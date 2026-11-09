import unittest

from shop.cart import Cart
from shop.checkout import checkout_total, format_total, tax_cents


class CheckoutTest(unittest.TestCase):
    def test_total_with_discount(self):
        cart = Cart()
        cart.add('book', 1000, 2)
        total = checkout_total(cart, {'percent': 10})
        self.assertIn('$', format_total(total))

    def test_tax(self):
        self.assertEqual(tax_cents(1000, 0.05), 50)


if __name__ == '__main__':
    unittest.main()
