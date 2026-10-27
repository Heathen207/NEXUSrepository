import unittest
from commerce import analyze

class CommerceAuditTests(unittest.TestCase):
    def test_duplicate_title_and_price_review(self):
        products = [
            {'id': 'a', 'title': 'Billy-Ometry Basketball Shorts', 'status': 'ACTIVE', 'productType': 'Shorts', 'variants': {'nodes': [{'price': '49.95'}]}},
            {'id': 'b', 'title': 'Billy-Ometry Basketball Shorts', 'status': 'ACTIVE', 'productType': 'Shorts', 'variants': {'nodes': [{'price': '40.00'}]}}
        ]
        flags = analyze(products)
        self.assertEqual(sum(item[2] == 'same_title' for item in flags), 2)
        self.assertEqual(sum(item[2] == 'review_shorts_price' for item in flags), 2)

    def test_never_flags_archived_price(self):
        flags = analyze([{'id': 'a', 'title': 'Old Basketball Shorts', 'status': 'ARCHIVED', 'productType': 'Shorts', 'variants': {'nodes': [{'price': '1.00'}]}}])
        self.assertFalse(any(item[2] == 'review_shorts_price' for item in flags))

if __name__ == '__main__':
    unittest.main()
