"""NEXUS COMMERCE: read-only Shopify catalog auditor.

Environment: SHOPIFY_SHOP=your-store.myshopify.com
             SHOPIFY_ADMIN_TOKEN=shpat_...
             SHOPIFY_API_VERSION=2026-07 (optional)
Uses Python's standard library only. Never writes to Shopify.
"""
import csv
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

QUERY = """query Products($cursor: String) {
 products(first: 100, after: $cursor) {
  pageInfo { hasNextPage endCursor }
  edges { node {
    id title handle status productType vendor
    variants(first: 50) { nodes { id title price sku } }
  } }
 }
}"""

def fetch_all():
    shop = os.environ.get("SHOPIFY_SHOP", "").strip().replace("https://", "").strip("/")
    token = os.environ.get("SHOPIFY_ADMIN_TOKEN", "").strip()
    version = os.environ.get("SHOPIFY_API_VERSION", "2026-07")
    if not shop or not token:
        raise RuntimeError("Set SHOPIFY_SHOP and SHOPIFY_ADMIN_TOKEN environment variables.")
    if not shop.endswith(".myshopify.com"):
        raise RuntimeError("Use the store's .myshopify.com domain, not the public storefront URL.")
    url = f"https://{shop}/admin/api/{version}/graphql.json"
    cursor, results = None, []
    while True:
        payload = json.dumps({"query": QUERY, "variables": {"cursor": cursor}}).encode()
        req = Request(url, data=payload, headers={
            "Content-Type": "application/json",
            "X-Shopify-Access-Token": token,
        }, method="POST")
        with urlopen(req, timeout=30) as res:
            data = json.load(res)
        if data.get("errors"):
            raise RuntimeError(f"Shopify query rejected: {data['errors']}")
        block = data.get("data", {}).get("products", {})
        results.extend(edge["node"] for edge in block.get("edges", []))
        page = block.get("pageInfo", {})
        if not page.get("hasNextPage"):
            break
        cursor = page.get("endCursor")
        if not cursor:
            raise RuntimeError("Shopify reported another page without a cursor.")
    return results

def analyze(products):
    issues = []
    titles = defaultdict(list)
    for p in products:
        if p["status"] != "ARCHIVED":
            titles[p["title"].strip().casefold()].append(p)
        if not (p.get("productType") or "").strip():
            issues.append((p["id"], p["title"], "missing_type", "Missing product type"))
        if p.get("status") != "ACTIVE":
            continue
        variants = p.get("variants", {}).get("nodes", [])
        if not variants:
            issues.append((p["id"], p["title"], "no_variants", "No variants returned"))
        prices = {v.get("price") for v in variants}
        if len(prices) > 1:
            issues.append((p["id"], p["title"], "variant_price_variation",
                           "Variant prices: " + ", ".join(sorted(prices))))
        if "short" in p["title"].lower() and "basketball" in p["title"].lower():
            try:
                if variants and float(variants[0]["price"]) != 46:
                    issues.append((p["id"], p["title"], "review_shorts_price",
                                   f"Listed at {variants[0]['price']}; prior target $46 needs cost verification"))
            except (ValueError, TypeError, KeyError):
                pass
    for title, matches in titles.items():
        if len(matches) > 1:
            for p in matches:
                issues.append((p["id"], p["title"], "same_title",
                               f"{len(matches)} non-archived products share this title; verify designs before editing"))
    return issues

def main():
    try:
        products = fetch_all()
    except (RuntimeError, HTTPError, URLError) as exc:
        print(f"COMMERCE audit could not connect: {exc}", file=sys.stderr)
        return 1
    issues = analyze(products)
    folder = Path("reports")
    folder.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    output = folder / f"commerce_audit_{stamp}.csv"
    with output.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["product_id", "product_title", "issue", "recommendation"])
        writer.writerows(issues)
    print(f"Checked {len(products)} products; found {len(issues)} review flags. Report: {output}")
    print("Read-only: no Shopify changes were made.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
