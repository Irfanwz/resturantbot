from decimal import Decimal


def calculate_tax(subtotal: Decimal, tax_rate: Decimal) -> Decimal:
    return (subtotal * tax_rate).quantize(Decimal("0.01"))


def calculate_total(subtotal: Decimal, tax: Decimal, delivery_fee: Decimal = Decimal("0.00")) -> Decimal:
    return subtotal + tax + delivery_fee
