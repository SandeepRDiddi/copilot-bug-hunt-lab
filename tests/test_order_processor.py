from decimal import Decimal

import pytest

from fixed_order_processor import calculate_discounted_total, process_orders


def test_calculate_discounted_total_happy_path():
    items = [{"name": "Laptop", "price": "1000.00", "qty": 1}]
    coupon = {"code": "SAVE20", "percent": 20, "expires_at": "2099-01-01"}
    total = calculate_discounted_total(items, "enterprise", coupon)
    # enterprise 10% off -> 900, coupon 20% off -> 720
    assert total == Decimal("720.00")


def test_rejects_negative_qty():
    items = [{"name": "Mouse", "price": "25.00", "qty": -1}]
    with pytest.raises(ValueError, match="negative qty"):
        calculate_discounted_total(items, "premium")


def test_duplicate_order_id_fails():
    orders = [
        {
            "id": "A100",
            "items": [{"name": "Laptop", "price": "1000.00", "qty": 1}],
            "customer_type": "regular",
        },
        {
            "id": "A100",
            "items": [{"name": "Mouse", "price": "20.00", "qty": 1}],
            "customer_type": "regular",
        },
    ]
    with pytest.raises(ValueError, match="Duplicate order id"):
        process_orders(orders)


def test_process_orders_returns_stable_schema():
    orders = [
        {
            "id": "X1",
            "items": [{"name": "Keyboard", "price": "50.00", "qty": 2}],
            "customer_type": "premium",
            "coupon": None,
        }
    ]
    out = process_orders(orders)
    assert out == [{"order_id": "X1", "total": "95.00"}]


@pytest.mark.parametrize("coupon_percent", [0, 5, 25, 50, 100])
def test_coupon_percent_boundaries(coupon_percent):
    items = [{"name": "A", "price": "10.00", "qty": 2}]
    coupon = {"code": "B", "percent": coupon_percent, "expires_at": "2099-12-31"}
    total = calculate_discounted_total(items, "regular", coupon)
    assert Decimal("0.00") <= total <= Decimal("20.00")
