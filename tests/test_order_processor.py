from decimal import Decimal
from typing import Any, cast

import pytest

from buggy_order_processor import OrderResult
from buggy_order_processor import calculate_discounted_total as buggy_calc
from buggy_order_processor import process_orders as buggy_process
from fixed_order_processor import calculate_discounted_total, process_orders


def test_calculate_discounted_total_happy_path() -> None:
    items = [{"name": "Laptop", "price": "1000.00", "qty": 1}]
    coupon = {"code": "SAVE20", "percent": 20, "expires_at": "2099-01-01"}
    total = calculate_discounted_total(items, "enterprise", coupon)
    # enterprise 10% off -> 900, coupon 20% off -> 720
    assert total == Decimal("720.00")


def test_rejects_negative_qty() -> None:
    items = [{"name": "Mouse", "price": "25.00", "qty": -1}]
    with pytest.raises(ValueError, match="negative qty"):
        calculate_discounted_total(items, "premium")


def test_duplicate_order_id_fails() -> None:
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


def test_process_orders_returns_stable_schema() -> None:
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
def test_coupon_percent_boundaries(coupon_percent: int) -> None:
    items = [{"name": "A", "price": "10.00", "qty": 2}]
    coupon = {"code": "B", "percent": coupon_percent, "expires_at": "2099-12-31"}
    total = calculate_discounted_total(items, "regular", coupon)
    assert Decimal("0.00") <= total <= Decimal("20.00")


# ---------------------------------------------------------------------------
# T-09  Regression tests targeting buggy_order_processor (now fixed)
# ---------------------------------------------------------------------------


# --- C-01 regression: range(len+1) IndexError was crashing every call ---
def test_buggy_no_index_error_on_valid_items() -> None:
    items = [{"name": "Widget", "price": "10.00", "qty": 3}]
    total = buggy_calc(items, "regular")
    assert total == Decimal("30.00")


# --- C-02 regression: correct tier discount rates ---
def test_buggy_regular_tier_no_discount() -> None:
    items = [{"name": "A", "price": "100.00", "qty": 1}]
    assert buggy_calc(items, "regular") == Decimal("100.00")


def test_buggy_premium_tier_five_percent() -> None:
    items = [{"name": "A", "price": "100.00", "qty": 1}]
    assert buggy_calc(items, "premium") == Decimal("95.00")


def test_buggy_enterprise_tier_ten_percent() -> None:
    items = [{"name": "A", "price": "1200.00", "qty": 1}]
    assert buggy_calc(items, "enterprise") == Decimal("1080.00")


# --- C-03 regression: coupon is a percentage, not flat subtraction ---
def test_buggy_coupon_applied_as_percentage() -> None:
    items = [{"name": "A", "price": "200.00", "qty": 1}]
    coupon = {"percent": 10, "expires_at": "2099-01-01"}
    # regular (0% discount) -> 200; coupon 10% off -> 180
    assert buggy_calc(items, "regular", coupon) == Decimal("180.00")


# --- C-04 regression: Decimal arithmetic, no float rounding drift ---
def test_buggy_decimal_precision() -> None:
    items = [{"name": "A", "price": "0.10", "qty": 3}]
    total = buggy_calc(items, "regular")
    assert total == Decimal("0.30")


# --- C-05 regression: broad except removed; errors propagate ---
def test_buggy_process_orders_propagates_validation_error() -> None:
    orders = [
        {
            "id": "ERR1",
            "items": [{"name": "A", "price": "-1.00", "qty": 1}],
            "customer_type": "regular",
        }
    ]
    with pytest.raises(ValueError):
        buggy_process(orders)


# --- H-01 regression: duplicate IDs raise ValueError ---
def test_buggy_duplicate_order_id_raises() -> None:
    orders = [
        {
            "id": "D1",
            "items": [{"name": "A", "price": "10.00", "qty": 1}],
            "customer_type": "regular",
        },
        {
            "id": "D1",
            "items": [{"name": "B", "price": "5.00", "qty": 1}],
            "customer_type": "regular",
        },
    ]
    with pytest.raises(ValueError, match="Duplicate order id"):
        buggy_process(orders)


# --- H-02 regression: negative price rejected ---
def test_buggy_rejects_negative_price() -> None:
    items = [{"name": "Bad", "price": "-5.00", "qty": 1}]
    with pytest.raises(ValueError):
        buggy_calc(items, "regular")


# --- H-03 regression: empty items list raises ---
def test_buggy_empty_items_raises() -> None:
    with pytest.raises(ValueError):
        buggy_calc([], "regular")


# --- H-04 regression: unknown customer_type raises ---
def test_buggy_unknown_customer_type_raises() -> None:
    items = [{"name": "A", "price": "10.00", "qty": 1}]
    with pytest.raises(ValueError, match="Unknown customer_type"):
        buggy_calc(items, "vip")


# --- H-05 regression: expired coupon is not applied ---
def test_buggy_expired_coupon_not_applied() -> None:
    items = [{"name": "A", "price": "100.00", "qty": 1}]
    coupon = {"percent": 50, "expires_at": "2000-01-01"}
    # Coupon is expired; regular tier -> no discount -> 100.00
    assert buggy_calc(items, "regular", coupon) == Decimal("100.00")


# --- H-06 regression: total can never be negative ---
def test_buggy_total_floor_at_zero() -> None:
    items = [{"name": "A", "price": "1.00", "qty": 1}]
    coupon = {"percent": 100, "expires_at": "2099-01-01"}
    total = buggy_calc(items, "regular", coupon)
    assert total >= Decimal("0.00")


# --- H-07 / H-08 regression: return schema keys ---
def test_buggy_process_orders_stable_schema() -> None:
    orders = [
        {
            "id": "S1",
            "items": [{"name": "A", "price": "50.00", "qty": 2}],
            "customer_type": "regular",
        }
    ]
    result = buggy_process(orders)
    assert result == [OrderResult(order_id="S1", total=Decimal("100.00"))]


# --- H-09 regression: malformed coupon raises ---
def test_buggy_coupon_missing_percent_raises() -> None:
    items = [{"name": "A", "price": "10.00", "qty": 1}]
    with pytest.raises(ValueError):
        buggy_calc(items, "regular", {"expires_at": "2099-01-01"})


def test_buggy_coupon_out_of_range_raises() -> None:
    items = [{"name": "A", "price": "10.00", "qty": 1}]
    with pytest.raises(ValueError):
        buggy_calc(items, "regular", {"percent": 150, "expires_at": "2099-01-01"})



# --- Additional Coverage Tests ---

def test_validate_missing_name() -> None:
    """Test validation for missing 'name' key in item."""
    items = [{"price": "10.00", "qty": 1}]
    with pytest.raises(ValueError, match="missing required keys"):
        calculate_discounted_total(items, "regular")


def test_validate_invalid_name() -> None:
    """Test validation for empty/invalid name."""
    items = [{"name": "", "price": "10.00", "qty": 1}]
    with pytest.raises(ValueError, match="invalid name"):
        calculate_discounted_total(items, "regular")


def test_validate_missing_price() -> None:
    """Test validation for missing 'price' key."""
    items = [{"name": "Widget", "qty": 1}]
    with pytest.raises(ValueError, match="missing required keys"):
        calculate_discounted_total(items, "regular")


def test_validate_missing_qty() -> None:
    """Test validation for missing 'qty' key."""
    items = [{"name": "Widget", "price": "10.00"}]
    with pytest.raises(ValueError, match="missing required keys"):
        calculate_discounted_total(items, "regular")


def test_item_not_dict() -> None:
    """Test that items must be dicts."""
    items: Any = ["not a dict"]
    with pytest.raises(ValueError, match="must be a dict"):
        calculate_discounted_total(items, "regular")


def test_coupon_not_dict() -> None:
    """Test that coupon must be a dict if provided."""
    items = [{"name": "Widget", "price": "10.00", "qty": 1}]
    with pytest.raises(ValueError, match="coupon must be a dict"):
        calculate_discounted_total(items, "regular", coupon=cast(Any, "not a dict"))


def test_coupon_missing_expires_at() -> None:
    """Test that coupon must have both percent and expires_at."""
    items = [{"name": "Widget", "price": "10.00", "qty": 1}]
    with pytest.raises(ValueError, match="coupon requires"):
        calculate_discounted_total(items, "regular", coupon={"percent": 10})


def test_coupon_negative_percent() -> None:
    """Test that coupon percent cannot be negative."""
    items = [{"name": "Widget", "price": "10.00", "qty": 1}]
    coupon = {"percent": -5, "expires_at": "2099-01-01"}
    with pytest.raises(ValueError, match="coupon percent must be in"):
        calculate_discounted_total(items, "regular", coupon=coupon)


def test_coupon_expiry_format_invalid() -> None:
    """Test that coupon expiry must be valid YYYY-MM-DD."""
    items = [{"name": "Widget", "price": "10.00", "qty": 1}]
    coupon = {"percent": 10, "expires_at": "invalid-date"}
    with pytest.raises(ValueError, match="Coupon expiry must be YYYY-MM-DD"):
        calculate_discounted_total(items, "regular", coupon=coupon)


def test_total_goes_negative_floored() -> None:
    """Test that total is floored at 0 when discounts exceed subtotal."""
    items = [{"name": "Widget", "price": "1.00", "qty": 1}]
    coupon = {"percent": 100, "expires_at": "2099-12-31"}
    result = calculate_discounted_total(items, "regular", coupon)
    assert result == Decimal("0.00")


def test_process_orders_not_list() -> None:
    """Test that orders must be a list."""
    with pytest.raises(ValueError, match="orders must be a list"):
        process_orders(cast(Any, "not a list"))


def test_process_order_not_dict() -> None:
    """Test that each order must be a dict."""
    orders: Any = ["not a dict"]
    with pytest.raises(ValueError, match="must be a dict"):
        process_orders(orders)


def test_process_order_missing_id() -> None:
    """Test that each order must have 'id'."""
    orders = [
        {
            "items": [{"name": "Widget", "price": "10.00", "qty": 1}],
            "customer_type": "regular",
        }
    ]
    with pytest.raises(ValueError, match="missing required keys"):
        process_orders(orders)


def test_process_order_missing_items() -> None:
    """Test that each order must have 'items'."""
    orders = [
        {
            "id": "O1",
            "customer_type": "regular",
        }
    ]
    with pytest.raises(ValueError, match="missing required keys"):
        process_orders(orders)


def test_process_order_missing_customer_type() -> None:
    """Test that each order must have 'customer_type'."""
    orders = [
        {
            "id": "O1",
            "items": [{"name": "Widget", "price": "10.00", "qty": 1}],
        }
    ]
    with pytest.raises(ValueError, match="missing required keys"):
        process_orders(orders)


def test_process_orders_empty_list() -> None:
    """Test that empty orders list returns empty results."""
    result = process_orders([])
    assert result == []


def test_coupon_with_zero_percent() -> None:
    """Test that 0% coupon has no effect."""
    items = [{"name": "Widget", "price": "100.00", "qty": 1}]
    coupon = {"percent": 0, "expires_at": "2099-12-31"}
    result = calculate_discounted_total(items, "regular", coupon)
    assert result == Decimal("100.00")


def test_validate_item_negative_qty_zero() -> None:
    """Test that zero qty is valid but contributes 0 to total."""
    items = [
        {"name": "Widget", "price": "100.00", "qty": 0},
        {"name": "Gadget", "price": "50.00", "qty": 1},
    ]
    result = calculate_discounted_total(items, "regular")
    assert result == Decimal("50.00")


def test_items_with_none_coupon() -> None:
    """Test that None coupon is treated as no coupon."""
    items = [{"name": "Widget", "price": "100.00", "qty": 1}]
    result = calculate_discounted_total(items, "regular", coupon=None)
    assert result == Decimal("100.00")
