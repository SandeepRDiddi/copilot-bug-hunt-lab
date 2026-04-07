from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Any


TWO_PLACES = Decimal("0.01")

DISCOUNT_BY_TIER = {
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


def _parse_expiry(expiry: str) -> date:
    try:
        yyyy, mm, dd = expiry.split("-")
        return date(int(yyyy), int(mm), int(dd))
    except Exception as exc:
        raise ValueError("Coupon expiry must be YYYY-MM-DD.") from exc


def calculate_discounted_total(
    items: list[dict[str, Any]],
    customer_type: str,
    coupon: dict[str, Any] | None = None,
) -> Decimal:
    """
    Returns a two-decimal money value as Decimal.
    Raises ValueError for invalid inputs.
    """
    if customer_type not in DISCOUNT_BY_TIER:
        raise ValueError(f"Unknown customer_type: {customer_type}")
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
            raise ValueError("coupon requires percent and expires_at.")
        percent = _to_decimal(coupon["percent"])
        if percent < 0 or percent > 100:
            raise ValueError("coupon percent must be in [0, 100].")
        expiry = _parse_expiry(str(coupon["expires_at"]))
        if expiry >= date.today():
            total *= Decimal("1") - (percent / Decimal("100"))

    if total < 0:
        total = Decimal("0")
    return total.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def process_orders(orders: list[dict[str, Any]]) -> list[dict[str, str]]:
    """
    Stable return schema:
    [
      {"order_id": "A100", "total": "1080.00"},
      ...
    ]
    """
    if not isinstance(orders, list):
        raise ValueError("orders must be a list.")

    results: list[dict[str, str]] = []
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
        results.append({"order_id": order_id, "total": f"{total:.2f}"})

    return results
