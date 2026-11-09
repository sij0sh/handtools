"""Checkout totals, tax and refunds, in integer cents."""
from .pricing import apply_discount, round_cents


def validate_discount(discount):
    if not isinstance(discount, dict) or not 0 <= discount.get('percent', -1) <= 100:
        raise ValueError('invalid discount')
    return discount


def checkout_total(cart, discount=None):
    subtotal = sum(i['price_cents'] * i['qty'] for i in cart.items)
    if discount is None:
        return subtotal
    return apply_discount(subtotal, validate_discount(discount))


def tax_cents(total_cents, rate):
    """Tax on a total at `rate` (0.0825 = 8.25%), rounded half up to a cent."""
    return round_cents(total_cents * rate)


def format_total(total_cents):
    return f'${total_cents // 100}.{total_cents % 100:02d}'


def refund(order_total_cents, refunded_cents, amount_cents):
    """Refund up to what remains of the order; never zero or negative."""
    remaining = order_total_cents - refunded_cents
    if amount_cents <= 0 or amount_cents > remaining:
        raise ValueError('invalid refund')
    return amount_cents
