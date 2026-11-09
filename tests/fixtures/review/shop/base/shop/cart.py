"""A cart of line items: {"sku", "price_cents", "qty"}."""


class Cart:
    def __init__(self):
        self.items = []

    def add(self, sku, price_cents, qty=1):
        if qty < 1:
            raise ValueError('qty must be positive')
        self.items.append({'sku': sku, 'price_cents': price_cents, 'qty': qty})

    def page(self, number, size):
        """Items on 1-based page `number` of `size` items."""
        start = number * size
        return self.items[start:start + size]
