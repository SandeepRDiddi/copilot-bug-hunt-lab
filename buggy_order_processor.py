from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

TWO_PLACES = Decimal("0.01")

DISCOUNT_BY_TIER: dict[str, Decimal] = {
    "regular": Decimal("0.00"),
    "premium": Decimal("0.05"),
    "enterprise": Decimal("0.10"),
}


@dataclass(frozen=True)
class OrderResult:
    order_id: str
    total: Decimal


def _to_decimal(value: Any) -> Decimal:
    return Decimal(str(value))


def _parse_expiry(expiry: str) -> date:
    try:
        yyyy, mm, dd = expiry.split("-")
        return date(int(yyyy), int(mm), int(dd))
    except Exception as exc:
        raise ValueError("Coupon expiry must be YYYY-MM-DD.") from exc


def _validate_item(item: dict[str, Any], index: int) -> None:
    required = {"name", "price", "qty"}
    missing = required - set(item.keys())
    if missing:
        raise ValueError(f"Item {index} is missing required keys: {sorted(missing)}")
    if not isinstance(item["name"], str) or not item["name"].strip():
        raise ValueError(f"Item {index} has invalid name.")
    if _to_decimal(item["price"]) < 0:
        raise ValueError(f"Item {index} has negative price.")
    if int(item["qty"]) < 0:
        raise ValueError(f"Item {index} has negative qty.")


def calculate_discounted_total(
    items: list[dict[str, Any]],
    customer_type: str,
    coupon: dict[str, Any] | None = None,
) -> Decimal:
    """Calculate the discounted total for a list of order items.

    Args:
        items: Non-empty list of item dicts; each must have "name" (str),
            "price" (non-negative numeric), and "qty" (non-negative int).
        customer_type: Customer tier — must be one of "regular", "premium",
            or "enterprise".
        coupon: Optional dict with "percent" (int in [0, 100]) and
            "expires_at" (str "YYYY-MM-DD"). Ignored if expired.

    Returns:
        Two-decimal-place Decimal total after tier and coupon discounts.
        Minimum returned value is Decimal("0.00").

    Raises:
        ValueError: For unknown customer_type, invalid items, negative
            price/qty, or malformed coupon data.
    """
    if customer_type not in DISCOUNT_BY_TIER:
        raise ValueError(f"Unknown customer_type: {customer_type!r}")
    if not isinstance(items, list) or not items:
        raise ValueError("items must be a non-empty list.")

    subtotal = Decimal("0")
    for idx, item in enumerate(items):
        if not isinstance(item, dict):
            raise ValueError(f"Item {idx} must be a dict.")
        _validate_item(item, idx)
        subtotal += _to_decimal(item["price"]) * _to_decimal(item["qty"])

    tier_discount_rate = DISCOUNT_BY_TIER[customer_type]
    total = subtotal * (Decimal("1") - tier_discount_rate)

    if coupon:
        if not isinstance(coupon, dict):
            raise ValueError("coupon must be a dict when provided.")
        if "percent" not in coupon or "expires_at" not in coupon:
            raise ValueError("coupon requires 'percent' and 'expires_at'.")
        percent = _to_decimal(coupon["percent"])
        if percent < 0 or percent > 100:
            raise ValueError("coupon percent must be in [0, 100].")
        expiry = _parse_expiry(str(coupon["expires_at"]))
        if expiry > date.today():
            total *= Decimal("1") - (percent / Decimal("100"))

    if total < 0:
        total = Decimal("0")
    return total.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def process_orders(orders: list[dict[str, Any]]) -> list[OrderResult]:
    """Process a batch of orders and return stable-schema results.

    Args:
        orders: List of order dicts; each must have "id" (str),
            "items" (list), and "customer_type" (str). Optional "coupon" key.

    Returns:
        List of OrderResult objects with exactly two fields: order_id (str)
        and total (Decimal with 2 decimal places).

    Raises:
        ValueError: If orders is not a list, contains duplicate IDs,
            is missing required keys, or any order fails validation.
    """
    if not isinstance(orders, list):
        raise ValueError("orders must be a list.")

    results: list[OrderResult] = []
    seen_ids: set[str] = set()

    for i, order in enumerate(orders):
        if not isinstance(order, dict):
            raise ValueError(f"Order index {i} must be a dict.")
        if "id" not in order or "items" not in order or "customer_type" not in order:
            raise ValueError(f"Order index {i} is missing required keys.")

        order_id = str(order["id"])
        if order_id in seen_ids:
            raise ValueError(f"Duplicate order id: {order_id}")
        seen_ids.add(order_id)

        total = calculate_discounted_total(
            items=order["items"],
            customer_type=str(order["customer_type"]),
            coupon=order.get("coupon"),
        )
        results.append(OrderResult(order_id=order_id, total=total))

    return results


if __name__ == "__main__":
    demo_orders: list[dict[str, Any]] = [
        {
            "id": "A100",
            "items": [{"name": "Laptop", "price": 1200.0, "qty": 1}],
            "customer_type": "enterprise",
            "coupon": {"percent": 20, "expires_at": "2020-01-01"},
        },
    ]

    print(process_orders(demo_orders))
