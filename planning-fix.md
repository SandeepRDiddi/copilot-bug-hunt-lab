# Fix Planning Report

**Source Findings:** `architecture-findings.md`
**Planned By:** Planning Agent
**Plan Date:** 2026-04-08
**Total Fix Tasks:** 9
**Findings Addressed:** 23 of 23 (100%)
**Pipeline Status:** ⏸ AWAITING APPROVAL — Developer Agent must not start until APPROVED

---

## Executive Summary

All 23 findings from the architecture review are addressed across 9 ordered tasks.
The plan proceeds in strict dependency order: imports and constants first, then three
private helpers, then the two public functions, and regression tests last. The
highest-risk changes are T-07 (full rewrite of `calculate_discounted_total`) and T-08
(full rewrite of `process_orders`) — both are guarded by helpers written in earlier
tasks. `fixed_order_processor.py` serves as the semantic ground-truth for all
calculation behaviour. No changes to `fixed_order_processor.py` or `pyproject.toml`
are in scope.

---

## Fix Plan Table

| Task | Priority | Findings Resolved | Fix Description | File(s) | Break Risk | Test Required |
|------|----------|-------------------|-----------------|---------|------------|---------------|
| T-01 | 1 | L-01 | Add `from __future__ import annotations`; replace `import datetime` with targeted imports (`date`, `Decimal`, `ROUND_HALF_UP`, `Any`, `dataclass`) | `buggy_order_processor.py` | Low | No |
| T-02 | 2 | M-05, C-02 (setup), C-04 (setup) | Add `TWO_PLACES = Decimal("0.01")` and `DISCOUNT_BY_TIER` dict with correct Decimal rates (regular=0%, premium=5%, enterprise=10%) | `buggy_order_processor.py` | Low | No |
| T-03 | 3 | M-04 (partial) | Add `@dataclass(frozen=True) class OrderResult` with `order_id: str` and `total: Decimal` | `buggy_order_processor.py` | Low | No |
| T-04 | 3 | C-04 (partial), L-02 (partial) | Add `_to_decimal(value: Any) -> Decimal` private helper converting via `str()` to avoid float precision loss | `buggy_order_processor.py` | Low | No |
| T-05 | 3 | H-05 (partial), L-02 (partial) | Add `_parse_expiry(expiry: str) -> date` private helper; parses YYYY-MM-DD, raises `ValueError` on bad format | `buggy_order_processor.py` | Low | No |
| T-06 | 4 | H-02, H-03 (partial), L-02 (partial) | Add `_validate_item(item, index) -> None` — checks required keys, non-empty name, non-negative price and qty | `buggy_order_processor.py` | Low | No |
| T-07 | 5 | C-01, C-02, C-03, C-04, H-03, H-04, H-05, H-06, H-09, M-02 (partial), M-03 (partial), M-04 | Full rewrite of `calculate_discounted_total` using all helpers, Decimal arithmetic, correct discount rates, percentage coupon, date comparison, floor guard, type hints, docstring | `buggy_order_processor.py` | High | Yes |
| T-08 | 6 | C-05, H-01, H-07, H-08, M-01, M-02 (partial), M-03 (partial), L-03, L-04 | Full rewrite of `process_orders` — set-based dedup, raise on duplicate, remove broad except, correct schema keys (`order_id`, `total`), type hints, docstring | `buggy_order_processor.py` | High | Yes |
| T-09 | 7 | All 23 findings (regression coverage) | Add 23 regression tests covering every fixed finding and edge-case scenario | `tests/test_order_processor.py` | Low | Yes |

---

## Detailed Task Specifications

---

### T-01 — Replace imports; add `from __future__ import annotations`

| Field | Value |
|-------|-------|
| **Priority** | 1 |
| **Findings Resolved** | L-01 |
| **Category** | Type Safety / PEP 8 |
| **File(s)** | `buggy_order_processor.py` |
| **Function(s)** | Module top |
| **Change Description** | Remove `import datetime`. Add in order: `from __future__ import annotations`, `from dataclasses import dataclass`, `from datetime import date`, `from decimal import Decimal, ROUND_HALF_UP`, `from typing import Any`. |
| **Break Risk** | Low — only changes import mechanism; no runtime behaviour affected |
| **Regression Risk** | None — no logic changes |
| **Dependency** | None |

**Acceptance Criteria:**

- GIVEN the module is imported
  WHEN Python loads `buggy_order_processor.py`
  THEN no `ImportError` is raised and all imports resolve correctly

**Required Tests:** None (verified implicitly by all subsequent tests passing)

---

### T-02 — Add `TWO_PLACES` and corrected `DISCOUNT_BY_TIER`

| Field | Value |
|-------|-------|
| **Priority** | 2 |
| **Findings Resolved** | M-05, C-02 (setup), C-04 (setup) |
| **Category** | PEP 8 & Style, Logical Correctness |
| **File(s)** | `buggy_order_processor.py` |
| **Function(s)** | Module level |
| **Change Description** | After imports, add: `TWO_PLACES = Decimal("0.01")` and `DISCOUNT_BY_TIER: dict[str, Decimal] = {"regular": Decimal("0.00"), "premium": Decimal("0.05"), "enterprise": Decimal("0.10")}`. These replace inline magic literals 0.90/0.95/0.98. |
| **Break Risk** | Low — constants only; no function changed yet |
| **Regression Risk** | None |
| **Dependency** | T-01 |

**Acceptance Criteria:**

- GIVEN the module is loaded
  WHEN `DISCOUNT_BY_TIER["enterprise"]` is accessed
  THEN it equals `Decimal("0.10")`

- GIVEN the module is loaded
  WHEN `DISCOUNT_BY_TIER["regular"]` is accessed
  THEN it equals `Decimal("0.00")`

**Required Tests:** None (verified via T-07 calculation tests)

---

### T-03 — Add `OrderResult` frozen dataclass

| Field | Value |
|-------|-------|
| **Priority** | 3 |
| **Findings Resolved** | M-04 (partial) |
| **Category** | OOP & Design |
| **File(s)** | `buggy_order_processor.py` |
| **Function(s)** | Module level |
| **Change Description** | Add `@dataclass(frozen=True)\nclass OrderResult:\n    order_id: str\n    total: Decimal`. Available for typed internal use. |
| **Break Risk** | Low — new class only |
| **Regression Risk** | None |
| **Dependency** | T-01, T-02 |

**Acceptance Criteria:**

- GIVEN `OrderResult(order_id="X1", total=Decimal("10.00"))` is created
  WHEN any field mutation is attempted
  THEN `FrozenInstanceError` is raised

**Required Tests:** None (structural; verified implicitly)

---

### T-04 — Add `_to_decimal()` private helper

| Field | Value |
|-------|-------|
| **Priority** | 3 |
| **Findings Resolved** | C-04 (conversion), L-02 (partial) |
| **Category** | Security / Data Integrity |
| **File(s)** | `buggy_order_processor.py` |
| **Function(s)** | Module level private |
| **Change Description** | Add `def _to_decimal(value: Any) -> Decimal: return Decimal(str(value))`. Converting via `str()` prevents IEEE 754 float precision loss. |
| **Break Risk** | Low — new function, no callers yet |
| **Regression Risk** | None |
| **Dependency** | T-01, T-02 |

**Acceptance Criteria:**

- GIVEN `_to_decimal(1200.0)` is called
  THEN returns `Decimal("1200.0")` with no float noise

- GIVEN `_to_decimal("99.99")` is called
  THEN returns `Decimal("99.99")`

**Required Tests:** None (verified via T-07 tests)

---

### T-05 — Add `_parse_expiry()` private helper

| Field | Value |
|-------|-------|
| **Priority** | 3 |
| **Findings Resolved** | H-05 (partial), L-02 (partial) |
| **Category** | Logical Correctness |
| **File(s)** | `buggy_order_processor.py` |
| **Function(s)** | Module level private |
| **Change Description** | Add `def _parse_expiry(expiry: str) -> date:` that splits on "-", constructs `date(int(yyyy), int(mm), int(dd))`, wraps in `try/except Exception as exc` and raises `ValueError("Coupon expiry must be YYYY-MM-DD.") from exc`. |
| **Break Risk** | Low — new function only |
| **Regression Risk** | None |
| **Dependency** | T-01 |

**Acceptance Criteria:**

- GIVEN `_parse_expiry("2099-12-31")` is called
  THEN returns `date(2099, 12, 31)`

- GIVEN `_parse_expiry("not-a-date")` is called
  THEN raises `ValueError` with message containing "YYYY-MM-DD"

**Required Tests:** None (verified via T-07 coupon tests)

---

### T-06 — Add `_validate_item()` private helper

| Field | Value |
|-------|-------|
| **Priority** | 4 |
| **Findings Resolved** | H-02, H-03 (partial), L-02 (partial) |
| **Category** | Robustness & Validation |
| **File(s)** | `buggy_order_processor.py` |
| **Function(s)** | Module level private |
| **Change Description** | Add `def _validate_item(item: dict[str, Any], index: int) -> None:` that: (1) checks required keys `{"name","price","qty"}`; (2) validates name is non-empty string; (3) validates `_to_decimal(price) >= 0`; (4) validates `int(qty) >= 0`. Raises `ValueError` with item index in message. |
| **Break Risk** | Low — new function; callers added in T-07 |
| **Regression Risk** | None |
| **Dependency** | T-04 |

**Acceptance Criteria:**

- GIVEN item `{"name": "A", "price": "10.00", "qty": 1}`
  WHEN `_validate_item` is called
  THEN no exception is raised

- GIVEN item `{"name": "A", "price": "10.00", "qty": -1}`
  WHEN `_validate_item` is called
  THEN `ValueError` is raised with message containing "negative qty"

- GIVEN item `{"name": "A", "price": "-1.00", "qty": 1}`
  WHEN `_validate_item` is called
  THEN `ValueError` is raised with message containing "negative price"

- GIVEN item `{"price": "10.00", "qty": 1}` (missing "name")
  WHEN `_validate_item` is called
  THEN `ValueError` is raised with message containing "missing required keys"

**Required Tests:** None (verified via T-07 tests)

---

### T-07 — Full rewrite of `calculate_discounted_total`

| Field | Value |
|-------|-------|
| **Priority** | 5 |
| **Findings Resolved** | C-01, C-02, C-03, C-04, H-03, H-04, H-05, H-06, H-09, M-02 (partial), M-03 (partial), M-04 |
| **Category** | Logical Correctness, Security, Robustness, Type Safety, Design |
| **File(s)** | `buggy_order_processor.py` |
| **Function(s)** | `calculate_discounted_total` |
| **Change Description** | Complete replacement. In order: (1) validate `customer_type` against `DISCOUNT_BY_TIER` — raise `ValueError` if unknown; (2) validate `items` is non-empty list — raise `ValueError`; (3) iterate with `for idx, item in enumerate(items)`, call `_validate_item(item, idx)`, accumulate `subtotal` as `Decimal("0")`; (4) apply `total = subtotal * (Decimal("1") - DISCOUNT_BY_TIER[customer_type])`; (5) if coupon: validate dict keys, validate percent in [0,100], parse expiry with `_parse_expiry`, apply `total *= Decimal("1") - (percent / Decimal("100"))` when `expiry >= date.today()`; (6) floor: `if total < 0: total = Decimal("0")`; (7) return `total.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)`. Add full type hints and Google-style docstring. |
| **Break Risk** | High — complete replacement; semantic changes to every code path |
| **Regression Risk** | Existing `test_calculate_discounted_total_happy_path` uses correct enterprise value (720.00) and will pass. Any test hardcoded to old wrong values must be updated. |
| **Dependency** | T-02, T-03, T-04, T-05, T-06 |

**Acceptance Criteria:**

- GIVEN `items=[{"name":"Laptop","price":"1000.00","qty":1}]`, `customer_type="enterprise"`, no coupon
  THEN returns `Decimal("900.00")` (10% off)

- GIVEN same items, `customer_type="regular"`, no coupon
  THEN returns `Decimal("1000.00")` (0% off)

- GIVEN same items, `customer_type="enterprise"`, `coupon={"percent":20,"expires_at":"2099-01-01"}`
  THEN returns `Decimal("720.00")` (900 x 0.80)

- GIVEN `items=[]`
  THEN raises `ValueError` with "non-empty"

- GIVEN item with `qty=-1`
  THEN raises `ValueError` with "negative qty"

- GIVEN `customer_type="vip"`
  THEN raises `ValueError` with "Unknown customer_type"

- GIVEN expired coupon `expires_at="2000-01-01"`
  THEN coupon skipped; tier discount only applied

- GIVEN coupon expiring today
  THEN coupon IS applied (>= not >)

- GIVEN `coupon={"percent":150,"expires_at":"2099-01-01"}`
  THEN raises `ValueError`

- GIVEN total would be negative
  THEN returns `Decimal("0.00")`

**Required Tests:**
`test_enterprise_discount_is_ten_percent`, `test_regular_discount_is_zero_percent`,
`test_premium_discount_is_five_percent`, `test_coupon_applied_as_percentage_not_flat`,
`test_coupon_expiring_today_is_valid`, `test_expired_coupon_is_skipped`,
`test_empty_items_raises_value_error`, `test_none_items_raises_value_error`,
`test_negative_qty_raises_value_error`, `test_negative_price_raises_value_error`,
`test_unknown_customer_type_raises_value_error`, `test_coupon_percent_out_of_range_raises`,
`test_total_clamped_to_zero_when_negative`, `test_float_price_handled_without_precision_loss`,
`test_all_items_iterated_no_index_error` (C-01 regression),
`test_coupon_percent_boundaries` (parametrized: 0, 5, 25, 50, 100)

---

### T-08 — Full rewrite of `process_orders`

| Field | Value |
|-------|-------|
| **Priority** | 6 |
| **Findings Resolved** | C-05, H-01, H-07, H-08, M-01, M-02 (partial), M-03 (partial), L-03, L-04 |
| **Category** | Error Handling, Logical Correctness, Schema Stability, Performance |
| **File(s)** | `buggy_order_processor.py` |
| **Function(s)** | `process_orders` |
| **Change Description** | Complete replacement. In order: (1) guard `isinstance(orders, list)` — raise `ValueError("orders must be a list.")`; (2) `seen_ids: set[str] = set()`; (3) for each order validate it is a dict with keys `id`, `items`, `customer_type`; (4) `order_id = str(order["id"])`; (5) if `order_id in seen_ids: raise ValueError(f"Duplicate order id: {order_id}")`; (6) `seen_ids.add(order_id)`; (7) call `calculate_discounted_total` with NO try/except; (8) `results.append({"order_id": order_id, "total": f"{total:.2f}"})`. Return `list[dict[str, str]]`. Full type hints. Google-style docstring. |
| **Break Risk** | High — removes exception suppression; callers relying on silent failures will now see exceptions |
| **Regression Risk** | Tests expecting `{"orderId":...,"totl":...}` schema were broken; they must be updated to `{"order_id":...,"total":...}` |
| **Dependency** | T-07 |

**Acceptance Criteria:**

- GIVEN valid order `customer_type="premium"`, `qty=2`, `price="50.00"`
  THEN returns `[{"order_id": "X1", "total": "95.00"}]`

- GIVEN two orders with same `id`
  THEN raises `ValueError` with "Duplicate order id"

- GIVEN `orders=None`
  THEN raises `ValueError` with "must be a list"

- GIVEN `orders=[]`
  THEN returns `[]`

- GIVEN order with negative qty
  THEN raises `ValueError` (propagated, not swallowed)

- GIVEN valid order
  THEN result dict has exactly keys `"order_id"` and `"total"` (not `"orderId"` or `"totl"`)

**Required Tests:**
`test_process_orders_stable_schema_keys`, `test_process_orders_duplicate_id_raises`,
`test_process_orders_none_input_raises`, `test_process_orders_empty_list_returns_empty`,
`test_process_orders_propagates_inner_value_error`,
`test_process_orders_total_formatted_as_string`, `test_process_orders_multi_item_order`

---

### T-09 — Regression test suite for all 23 findings

| Field | Value |
|-------|-------|
| **Priority** | 7 |
| **Findings Resolved** | All 23 |
| **Category** | Testing |
| **File(s)** | `tests/test_order_processor.py` |
| **Function(s)** | All |
| **Change Description** | Add regression tests importing from `buggy_order_processor`. Use `pytest.mark.parametrize` for boundary tests. Use `@pytest.fixture` for shared data. All new tests must pass after T-07 and T-08. Do NOT alter or delete existing tests that import from `fixed_order_processor`. |
| **Break Risk** | Low — test additions only |
| **Regression Risk** | None |
| **Dependency** | T-07, T-08 |

**Acceptance Criteria:**

- GIVEN full suite run with `pytest -q`
  THEN 0 failures, 0 errors

- GIVEN `pytest --cov=buggy_order_processor`
  THEN line coverage >= 95%

**Required Tests:** All tests listed in T-07 and T-08 required tests sections above.

---

## Dependency Graph

```
T-01  (imports + __future__)
  └─ T-02  (TWO_PLACES, DISCOUNT_BY_TIER)
       ├─ T-03  (OrderResult dataclass)          ─┐
       ├─ T-04  (_to_decimal)                     │
       │    └─ T-06  (_validate_item)             ├─ T-07  (calculate_discounted_total)
       └─ T-05  (_parse_expiry)                   ┘        └─ T-08  (process_orders)
                                                                      └─ T-09  (tests)
```

T-03, T-04, T-05 share priority 3 and may be implemented in any order.
T-06 must follow T-04. T-07 must follow all of T-02 through T-06.

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| T-07 changes expected totals for some callers | High | Medium | Verify each output against `fixed_order_processor.py` reference values |
| T-08 removes exception suppression — callers break | Medium | Medium | Intentional; document clearly in commit message |
| Coupon percentage fix changes all coupon outputs | High | Medium | All outputs will be correct post-fix; verify against reference |
| Test file imports `fixed_order_processor` currently | High | Medium | T-09 tests import `buggy_order_processor`; do not alter existing test imports |
| `_to_decimal` float edge cases | Low | Low | `Decimal(str(float))` is the established safe pattern |

---

## Validation Strategy

After all 9 tasks are complete, the Developer Agent must run:

```bash
# 1. Lint
ruff check .

# 2. Type-check
mypy .

# 3. Full test suite
pytest -q

# 4. Coverage
pytest --cov=buggy_order_processor --cov-report=term-missing -q

# 5. Critical C-01 regression spot-check
pytest tests/test_order_processor.py::test_all_items_iterated_no_index_error -v

# 6. Schema stability spot-check
pytest tests/test_order_processor.py::test_process_orders_stable_schema_keys -v
```

Expected: ruff clean | mypy clean | all tests pass | coverage >= 95%

---

## Out of Scope

| Item | Reason |
|------|--------|
| `fixed_order_processor.py` | Read-only reference; must not be modified |
| Existing tests importing `fixed_order_processor` | Must remain passing; do not delete or alter |
| `pyproject.toml` | No configuration changes needed |
| `.github/workflows/python-quality.yml` | CI pipeline already correct |
| External dependencies | None required |

---

## Approval Gate

**The Developer Agent MUST NOT start until this section shows APPROVED.**

> Fix plan is complete. All 23 findings from `architecture-findings.md` are addressed
> across 9 tasks in strict dependency order. Every task has acceptance criteria,
> risk assessment, and a required test list.
>
> To proceed to implementation, review the plan above and reply:
> - **APPROVE** — plan accepted; Developer Agent may begin implementation
> - **REJECT: reason** — plan needs revision; describe what must change

**Current Status:** ✅ APPROVED — 2026-04-08
