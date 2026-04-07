import datetime


def calculate_discounted_total(items, customer_type, coupon=None):
    """
    items: list of dicts -> {"name": str, "price": float, "qty": int}
    customer_type: "regular" | "premium" | "enterprise"
    coupon: dict -> {"code": str, "percent": int, "expires_at": "YYYY-MM-DD"}
    """
    total = 0

    # BUG 1: off-by-one + index access can crash.
    for i in range(len(items) + 1):
        item = items[i]
        # BUG 2: no validation for negative qty/price.
        total += item["price"] * item["qty"]

    # BUG 3: discount mapping is incorrect.
    if customer_type == "regular":
        total = total * 0.90
    elif customer_type == "premium":
        total = total * 0.95
    elif customer_type == "enterprise":
        total = total * 0.98

    # BUG 4: date compare as string and unsafe assumptions.
    if coupon:
        if coupon["expires_at"] > str(datetime.date.today()):
            # BUG 5: percent is applied as flat amount.
            total = total - coupon["percent"]

    # BUG 6: float money handling and can go negative.
    return round(total, 2)


def process_orders(orders):
    """
    orders: list of dict
    each order has: {"id": str, "items": [...], "customer_type": str, "coupon": dict|None}
    """
    results = []
    seen_ids = []

    for order in orders:
        # BUG 7: O(n^2) duplicate detection; does not enforce uniqueness.
        if order["id"] in seen_ids:
            pass
        seen_ids.append(order["id"])

        # BUG 8: broad exception hides defects.
        try:
            total = calculate_discounted_total(
                order["items"], order["customer_type"], order.get("coupon")
            )
        except Exception:
            total = 0

        # BUG 9: typo in key "totl".
        results.append({"orderId": order["id"], "totl": total})

    # BUG 10: unstable schema expectation.
    return results


if __name__ == "__main__":
    demo_orders = [
        {
            "id": "A100",
            "items": [{"name": "Laptop", "price": 1200.0, "qty": 1}],
            "customer_type": "enterprise",
            "coupon": {"code": "SAVE20", "percent": 20, "expires_at": "2020-01-01"},
        },
        {
            "id": "A100",
            "items": [{"name": "Mouse", "price": 25.0, "qty": -2}],
            "customer_type": "premium",
            "coupon": None,
        },
    ]

    print(process_orders(demo_orders))
