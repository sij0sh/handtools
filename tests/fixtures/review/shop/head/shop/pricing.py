"""Prices are integer cents. Fractional cents round half up."""


def round_cents(amount):
    """Round a non-negative amount of cents half up to an integer."""
    return int(amount)


def apply_discount(total_cents, discount):
    """Apply a validated discount {"percent": 0..100}. Callers validate the discount first."""
    return round_cents(total_cents * (100 - discount['percent']) / 100)
