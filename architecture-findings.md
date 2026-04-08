# Architecture Findings Report

**Source File:** `buggy_order_processor.py`  
**Reviewed By:** Architecture Agent  
**Review Date:** 2026-04-08  
**Total Findings:** 23 (Critical: 5 | High: 9 | Medium: 5 | Low: 4)  
**Pipeline Status:** ⏸ AWAITING APPROVAL — Planning Agent must not proceed until APPROVED

---

## Executive Summary

`buggy_order_processor.py` contains **5 critical defects** that make the module
unfit for any production use in its current state. Every call to
`calculate_discounted_total` raises an `IndexError` (immediately masked by a broad
`except Exception` that silently returns `0`), meaning no order is ever correctly
processed. Financial calculations use `float` arithmetic, introducing IEEE 754
precision errors on all monetary values. Discount rates are mapped incorrectly
(enterprise customers receive 2% off instead of 10%), coupons are applied as flat
subtractions instead of percentages, and the return schema contains a key typo
(`"totl"`) that breaks every downstream caller. The code requires a full,
structured remediation before it can handle a single real order.

---

## Findings Table (Severity: Critical → Low)

| ID   | Severity | Category                 | Location                             | Description                                                                                  | Business Impact                                                                        |
|------|----------|--------------------------|--------------------------------------|----------------------------------------------------------------------------------------------|----------------------------------------------------------------------------------------|
| C-01 | Critical | Logical Correctness      | `calculate_discounted_total` L13     | `range(len(items) + 1)` iterates one past end of list — raises `IndexError` every call       | Every order calculation crashes; no total is ever computed correctly                   |
| C-02 | Critical | Logical Correctness      | `calculate_discounted_total` L19–24  | Discount multipliers wrong: regular→10% off, enterprise→2% off (should be 0% and 10%)       | Customers billed at wrong rates; enterprise over-charged, regular given free discount  |
| C-03 | Critical | Logical Correctness      | `calculate_discounted_total` L30     | `total - coupon["percent"]` is flat subtraction, not percentage multiplication               | 20% coupon on $1,000 order saves $20 instead of $200 — $180 error per transaction      |
| C-04 | Critical | Security / Data Integrity| `calculate_discounted_total` L10, 16 | `total = 0` (int→float) then float arithmetic throughout — IEEE 754 precision loss           | Non-deterministic rounding errors on all financial totals; unacceptable for billing    |
| C-05 | Critical | Error Handling           | `process_orders` L51–56             | `except Exception: total = 0` swallows every error including C-01's IndexError               | All order failures silently produce total=0; bad data enters results undetected        |
| H-01 | High     | Logical Correctness      | `process_orders` L46–48             | `if order["id"] in seen_ids: pass` — `pass` is a no-op; duplicates always processed          | Duplicate orders are double-billed; no uniqueness contract enforced                    |
| H-02 | High     | Robustness & Validation  | `calculate_discounted_total` L16     | No guard against negative `price` or `qty` values                                            | Negative qty creates phantom credits; negative price reduces totals incorrectly        |
| H-03 | High     | Robustness & Validation  | `calculate_discounted_total` L13     | No check that `items` is a non-empty list before iterating                                    | `None` raises TypeError; empty list silently returns $0 total                          |
| H-04 | High     | Robustness & Validation  | `calculate_discounted_total` L19–24  | Unknown `customer_type` silently falls through all branches; no discount, no error           | Invalid tiers accepted without error; misconfigured callers go undetected              |
| H-05 | High     | Logical Correctness      | `calculate_discounted_total` L28     | `coupon["expires_at"] > str(date.today())` uses `>` not `>=`; no date parsing or validation  | Coupon expiring today incorrectly rejected; malformed dates compare silently wrong     |
| H-06 | High     | Security / Data Integrity| `calculate_discounted_total` L30     | No floor guard after coupon subtraction — total can go negative                               | Negative order totals in downstream payment/ERP systems can trigger incorrect refunds  |
| H-07 | High     | Schema Stability         | `process_orders` L59                | Return key typo `"totl"` instead of `"total"`                                                | Every caller doing `result["total"]` receives KeyError; API is completely broken       |
| H-08 | High     | Schema Stability         | `process_orders` L59                | Return key `"orderId"` uses camelCase — violates PEP 8 and reference schema                  | Callers expecting `"order_id"` receive KeyError; schema inconsistent with reference    |
| H-09 | High     | Robustness & Validation  | `calculate_discounted_total` L27–30  | Coupon dict accessed without key validation; `percent` not range-checked against [0, 100]    | Missing key raises unhandled KeyError; percent > 100 produces negative total           |
| M-01 | Medium   | Performance              | `process_orders` L42–48             | `seen_ids = []` with `if id in seen_ids` is O(n²) membership test                            | Quadratic slowdown on large order batches; unacceptable at production scale            |
| M-02 | Medium   | Type Safety              | All public functions                 | No type hints on any public function                                                          | mypy cannot catch type errors; IDE tooling provides no autocomplete or safety net      |
| M-03 | Medium   | Docstring Coverage       | All public functions                 | Docstrings present but missing `Args:`, `Returns:`, `Raises:` sections (PEP 257)             | Maintainers must reverse-engineer intent; incorrect parameter use goes unnoticed       |
| M-04 | Medium   | OOP & Design (SRP)       | `calculate_discounted_total`         | One function handles: iteration, validation, discounting, coupon parsing, rounding           | Changes to any one concern risk breaking others; logic cannot be unit-tested in isolation |
| M-05 | Medium   | PEP 8 & Style            | `calculate_discounted_total` L20–24  | Magic literals `0.90`, `0.95`, `0.98` inline — no named constant for discount tier mapping   | Discount rates are not self-documenting; editing one rate risks editing the wrong line |
| L-01 | Low      | Type Safety              | Module top                           | Missing `from __future__ import annotations`                                                  | Forward references in type hints will fail on Python < 3.10                            |
| L-02 | Low      | OOP & Design             | Module level                         | No private helpers `_validate_item`, `_to_decimal`, `_parse_expiry`                          | Reusable logic inlined; cannot be independently tested or reused                       |
| L-03 | Low      | Robustness & Validation  | `process_orders` entry               | No guard that `orders` parameter is a `list` type                                             | Non-list input raises cryptic TypeError with no helpful message                        |
| L-04 | Low      | PEP 8 & Style            | `process_orders` L59                | `"orderId"` key is camelCase in a Python dict (style violation; functional impact in H-08)   | Style inconsistency signals unclear API ownership; schema confusion for integrators    |

---

## Detailed Findings

### C-01 — IndexError: off-by-one in `range()` crashes every order calculation

| Field               | Value |
|---------------------|-------|
| **Severity**        | Critical |
| **Category**        | Logical Correctness |
| **Location**        | `calculate_discounted_total`, line 13 |
| **Description**     | `range(len(items) + 1)` iterates from `0` to `len(items)` inclusive. On the final iteration `items[len(items)]` is out of bounds and raises `IndexError`. |
| **Root Cause**      | Incorrect upper bound: `+1` is superfluous. Correct form is `range(len(items))` or `for item in items`. |
| **Impact**          | Every call with a non-empty `items` list raises `IndexError`. No order total is ever computed. |
| **Fix Direction**   | Replace `for i in range(len(items) + 1): item = items[i]` with `for item in items:` (idiomatic Python). |
| **Reference**       | PEP 8 — "Don't use index variables when iterating directly over a sequence." |

---

### C-02 — Wrong discount rate mapping for all customer tiers

| Field               | Value |
|---------------------|-------|
| **Severity**        | Critical |
| **Category**        | Logical Correctness |
| **Location**        | `calculate_discounted_total`, lines 19–24 |
| **Description**     | Current multipliers: `regular`→0.90 (10% off), `premium`→0.95 (5% off), `enterprise`→0.98 (2% off). Correct: `regular`→0% off, `premium`→5% off, `enterprise`→10% off. |
| **Root Cause**      | Discount tier map was coded by hand without a reference table; `regular` given a discount it should not have, `enterprise` under-discounted. |
| **Impact**          | Regular customers under-billed by 10%. Enterprise customers paying 98% instead of contracted 90%. Both are billing violations. |
| **Fix Direction**   | Introduce `DISCOUNT_BY_TIER: dict[str, Decimal]` constant. Compute `total = subtotal * (1 - DISCOUNT_BY_TIER[customer_type])`. |
| **Reference**       | `fixed_order_processor.py` lines 11–15. |

---

### C-03 — Coupon applied as flat amount, not percentage

| Field               | Value |
|---------------------|-------|
| **Severity**        | Critical |
| **Category**        | Logical Correctness |
| **Location**        | `calculate_discounted_total`, line 30 |
| **Description**     | `total = total - coupon["percent"]` subtracts the raw integer (e.g. `20`) as a flat monetary amount rather than computing 20% of total. |
| **Root Cause**      | Misread semantics of `percent`; treated as a currency value instead of a rate. |
| **Impact**          | A "20% off" coupon on a $1,000 order saves $20 instead of $200 — $180 error per transaction. |
| **Fix Direction**   | `total *= Decimal("1") - (percent / Decimal("100"))`. |
| **Reference**       | `fixed_order_processor.py` line 83. |

---

### C-04 — Float arithmetic used for all monetary calculations

| Field               | Value |
|---------------------|-------|
| **Severity**        | Critical |
| **Category**        | Security / Data Integrity |
| **Location**        | `calculate_discounted_total`, lines 10, 16, 20–24 |
| **Description**     | `total = 0` (int, promoted to float on first multiply). All arithmetic uses Python `float`. `round(total, 2)` does not eliminate accumulated IEEE 754 errors. |
| **Root Cause**      | No `Decimal` type used anywhere; `float` is the path of least resistance. |
| **Impact**          | Non-deterministic rounding errors on all financial totals. `0.1 + 0.2 == 0.30000000000000004` in Python — unacceptable for any billing system. |
| **Fix Direction**   | Import `Decimal, ROUND_HALF_UP`. Use `Decimal("0")` for accumulator. Convert inputs with `Decimal(str(value))`. Finalise with `.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)`. |
| **Reference**       | Python docs — `decimal` module; PEP 327. |

---

### C-05 — Broad `except Exception` silently converts all failures to `total = 0`

| Field               | Value |
|---------------------|-------|
| **Severity**        | Critical |
| **Category**        | Error Handling |
| **Location**        | `process_orders`, lines 51–56 |
| **Description**     | `except Exception: total = 0` catches every possible exception — including the C-01 `IndexError` — and silently appends `{"orderId": id, "totl": 0}` to results. |
| **Root Cause**      | Defensive coding with no specific exception strategy; intended to "keep processing" but destroys data integrity instead. |
| **Impact**          | Every broken order produces a `0` total. Callers cannot distinguish a legitimate $0 order from a failed calculation. All other bugs in this file are invisible in production. |
| **Fix Direction**   | Remove the broad `except`. Let `ValueError` from validation propagate. The caller of `process_orders` should handle exceptions at the batch level. |
| **Reference**       | PEP 8 — "Bare `except:` clauses should be avoided." |

---

### H-01 — Duplicate order ID check is a no-op

| Field               | Value |
|---------------------|-------|
| **Severity**        | High |
| **Category**        | Logical Correctness |
| **Location**        | `process_orders`, lines 46–48 |
| **Description**     | `if order["id"] in seen_ids: pass` — the body `pass` does nothing. Execution always falls through to `seen_ids.append(order["id"])` and the order calculation. |
| **Root Cause**      | Developer wrote the detection condition but forgot to add `continue` or `raise` to actually prevent duplicate processing. |
| **Impact**          | Duplicate order IDs silently produce two entries in the result list — double-billing customers. |
| **Fix Direction**   | `if order_id in seen_ids: raise ValueError(f"Duplicate order id: {order_id}")`. Use `set[str]` for O(1) lookup. |
| **Reference**       | `fixed_order_processor.py` lines 111–113. |

---

### H-02 — No validation for negative `price` or `qty`

| Field               | Value |
|---------------------|-------|
| **Severity**        | High |
| **Category**        | Robustness & Validation |
| **Location**        | `calculate_discounted_total`, line 16 |
| **Description**     | `total += item["price"] * item["qty"]` accepts any numeric value including negatives. A `qty` of `-2` silently creates a negative contribution to the total. |
| **Root Cause**      | No input validation layer before arithmetic begins. |
| **Impact**          | Negative quantities create store credits, reducing order totals below zero without any error signal. |
| **Fix Direction**   | Add `_validate_item(item, idx)` raising `ValueError` for negative `price` or `qty`. |
| **Reference**       | `fixed_order_processor.py` lines 28–38. |

---

### H-03 — No guard for `None` or empty `items`

| Field               | Value |
|---------------------|-------|
| **Severity**        | High |
| **Category**        | Robustness & Validation |
| **Location**        | `calculate_discounted_total`, before line 13 |
| **Description**     | If `items` is `None`, line 13 raises `TypeError`. If `items` is `[]`, total stays `0` — silently returning a zero-total order with no error. |
| **Root Cause**      | No pre-condition check on the `items` parameter. |
| **Impact**          | `None` input raises cryptic `TypeError`; empty list silently produces $0 which may be confused with a legitimate zero-cost order. |
| **Fix Direction**   | `if not isinstance(items, list) or not items: raise ValueError("items must be a non-empty list.")` |
| **Reference**       | `fixed_order_processor.py` line 60. |

---

### H-04 — Unknown `customer_type` silently applies no discount

| Field               | Value |
|---------------------|-------|
| **Severity**        | High |
| **Category**        | Robustness & Validation |
| **Location**        | `calculate_discounted_total`, lines 19–24 |
| **Description**     | An unrecognised `customer_type` (e.g. `"vip"`, `""`, `None`) silently falls through all `if/elif` branches. No discount applied, no error raised. |
| **Root Cause**      | No allowlist validation against known customer tiers. |
| **Impact**          | Typos or misconfigured callers silently accepted. A "vip" tier with promised 20% discount receives 0%. |
| **Fix Direction**   | `if customer_type not in DISCOUNT_BY_TIER: raise ValueError(f"Unknown customer_type: {customer_type}")` |
| **Reference**       | `fixed_order_processor.py` lines 58–59. |

---

### H-05 — Coupon expiry: string comparison with wrong operator rejects valid coupons

| Field               | Value |
|---------------------|-------|
| **Severity**        | High |
| **Category**        | Logical Correctness |
| **Location**        | `calculate_discounted_total`, line 28 |
| **Description**     | Two bugs: (1) `>` instead of `>=` rejects coupons expiring today; (2) raw string compared to string — no date parsing, no format validation. |
| **Root Cause**      | String shortcut instead of proper date parsing. |
| **Impact**          | Coupons expiring today are rejected despite being valid per business rules. Malformed date strings compare silently incorrectly. |
| **Fix Direction**   | Parse with `_parse_expiry(str)` returning a `date` object. Compare `expiry >= date.today()`. |
| **Reference**       | `fixed_order_processor.py` lines 41–46, 82. |

---

### H-06 — Total can go negative — no floor guard

| Field               | Value |
|---------------------|-------|
| **Severity**        | High |
| **Category**        | Security / Data Integrity |
| **Location**        | `calculate_discounted_total`, line 30 |
| **Description**     | `total = total - coupon["percent"]` applies no floor. If `coupon["percent"]` exceeds `total`, the result is negative. |
| **Root Cause**      | No post-calculation minimum guard; compounded by C-03's flat subtraction. |
| **Impact**          | Negative order totals in downstream payment or ERP systems can trigger incorrect automatic refunds. |
| **Fix Direction**   | After all discounts: `if total < 0: total = Decimal("0")`. |
| **Reference**       | `fixed_order_processor.py` lines 85–86. |

---

### H-07 — Return key typo `"totl"` breaks all callers

| Field               | Value |
|---------------------|-------|
| **Severity**        | High |
| **Category**        | Schema Stability |
| **Location**        | `process_orders`, line 59 |
| **Description**     | `results.append({"orderId": order["id"], "totl": total})` — `"totl"` is a typo for `"total"`. |
| **Root Cause**      | Typographic error not caught by any static analysis (no type hints or schema enforcement). |
| **Impact**          | Every caller doing `result["total"]` receives `KeyError`. The API is non-functional for any consumer. |
| **Fix Direction**   | Change to `"total": f"{total:.2f}"` matching reference return schema. |
| **Reference**       | `fixed_order_processor.py` line 120. |

---

### H-08 — Return key `"orderId"` breaks API contract and violates PEP 8

| Field               | Value |
|---------------------|-------|
| **Severity**        | High |
| **Category**        | Schema Stability |
| **Location**        | `process_orders`, line 59 |
| **Description**     | Key `"orderId"` uses camelCase. Python convention (PEP 8) and the reference both use `"order_id"`. |
| **Root Cause**      | Copied from a JavaScript-style schema without PEP 8 normalisation. |
| **Impact**          | Callers expecting `result["order_id"]` receive `KeyError`. All existing tests will fail. |
| **Fix Direction**   | Change to `"order_id": order_id`. |
| **Reference**       | `fixed_order_processor.py` line 120. |

---

### H-09 — Coupon dict not validated; `percent` not range-checked

| Field               | Value |
|---------------------|-------|
| **Severity**        | High |
| **Category**        | Robustness & Validation |
| **Location**        | `calculate_discounted_total`, lines 27–30 |
| **Description**     | `coupon["expires_at"]` and `coupon["percent"]` accessed without checking the dict contains those keys. `percent` never validated against `[0, 100]`. |
| **Root Cause**      | No coupon input validation layer before key access. |
| **Impact**          | Missing key raises unhandled `KeyError`. `percent > 100` or negative `percent` produces extreme or negative totals. |
| **Fix Direction**   | Validate coupon keys and `0 <= percent <= 100` before use; raise `ValueError` on violation. |
| **Reference**       | `fixed_order_processor.py` lines 74–80. |

---

### M-01 — O(n²) list-based duplicate detection

| Field               | Value |
|---------------------|-------|
| **Severity**        | Medium |
| **Category**        | Performance |
| **Location**        | `process_orders`, lines 42, 46 |
| **Description**     | `seen_ids = []` with `if order["id"] in seen_ids` performs a linear scan for every order — O(n²) overall. |
| **Root Cause**      | List used where a set is appropriate. |
| **Impact**          | For 10,000 orders: ~50M comparisons vs ~10K with a set. Unacceptable at production batch scale. |
| **Fix Direction**   | `seen_ids: set[str] = set()` — O(1) membership test. |
| **Reference**       | `fixed_order_processor.py` line 103. |

---

### M-02 — No type hints on any public function

| Field               | Value |
|---------------------|-------|
| **Severity**        | Medium |
| **Category**        | Type Safety |
| **Location**        | All public functions |
| **Description**     | `calculate_discounted_total` and `process_orders` have no parameter or return type annotations. `mypy --strict` errors on both. |
| **Root Cause**      | Type hints not added during initial development. |
| **Impact**          | No static type checking; CI `mypy` gate fails; IDE provides no autocomplete or safety. |
| **Fix Direction**   | Add full type hints per PEP 484. See `fixed_order_processor.py` for reference signatures. |
| **Reference**       | PEP 484 — Type Hints. |

---

### M-03 — Docstrings missing `Args`, `Returns`, `Raises` sections

| Field               | Value |
|---------------------|-------|
| **Severity**        | Medium |
| **Category**        | Docstring Coverage (PEP 257) |
| **Location**        | `calculate_discounted_total` L5–9, `process_orders` L37–40 |
| **Description**     | Both functions have informal comment-style docstrings without structured `Args:`, `Returns:`, or `Raises:` sections. |
| **Root Cause**      | No PEP 257 / Google-style docstring conventions enforced. |
| **Impact**          | `help()`, `pydoc`, and IDEs cannot surface parameter descriptions; exceptions are undocumented. |
| **Fix Direction**   | Rewrite in Google style with `Args:`, `Returns:`, `Raises:` sections. |
| **Reference**       | PEP 257; Google Python Style Guide — Docstrings. |

---

### M-04 — `calculate_discounted_total` violates Single Responsibility Principle

| Field               | Value |
|---------------------|-------|
| **Severity**        | Medium |
| **Category**        | OOP & Design (SRP) |
| **Location**        | `calculate_discounted_total`, entire function |
| **Description**     | One function handles: (1) item iteration, (2) price calculation, (3) tier discount, (4) coupon parsing, (5) coupon discount application, (6) rounding. Six responsibilities. |
| **Root Cause**      | No decomposition into private helpers. |
| **Impact**          | Any change to one concern risks breaking others; individual behaviours cannot be unit-tested in isolation. |
| **Fix Direction**   | Extract `_validate_item()`, `_to_decimal()`, and `_parse_expiry()` as private helpers. |
| **Reference**       | `fixed_order_processor.py` lines 24–46. |

---

### M-05 — Magic literals for discount rates

| Field               | Value |
|---------------------|-------|
| **Severity**        | Medium |
| **Category**        | PEP 8 & Style |
| **Location**        | `calculate_discounted_total`, lines 20, 22, 24 |
| **Description**     | `0.90`, `0.95`, `0.98` are inline literals with no named constant. Business meaning is opaque; they are also wrong (see C-02). |
| **Root Cause**      | No module-level constants defined. |
| **Impact**          | Changing a discount rate requires hunting through the function body; risk of editing the wrong line. |
| **Fix Direction**   | Introduce `DISCOUNT_BY_TIER: dict[str, Decimal]` module-level constant. |
| **Reference**       | PEP 8 — "Constants are usually defined on a module level." |

---

### L-01 — Missing `from __future__ import annotations`

| Field               | Value |
|---------------------|-------|
| **Severity**        | Low |
| **Category**        | Type Safety |
| **Location**        | Module top |
| **Description**     | `from __future__ import annotations` is absent. Required for forward-reference type hints and consistent behaviour across Python 3.8–3.11. |
| **Fix Direction**   | Add as first import line. |
| **Reference**       | PEP 563 — Postponed Evaluation of Annotations. |

---

### L-02 — No private helper functions for reusable logic

| Field               | Value |
|---------------------|-------|
| **Severity**        | Low |
| **Category**        | OOP & Design |
| **Location**        | Module level |
| **Description**     | Validation, decimal conversion, and date parsing are all inlined or missing. Private helpers with `_` prefix would improve testability and reuse. |
| **Fix Direction**   | Extract `_validate_item()`, `_to_decimal()`, `_parse_expiry()` as module-level private functions. |
| **Reference**       | `fixed_order_processor.py` lines 24–46. |

---

### L-03 — No type guard on `orders` parameter

| Field               | Value |
|---------------------|-------|
| **Severity**        | Low |
| **Category**        | Robustness & Validation |
| **Location**        | `process_orders`, entry |
| **Description**     | No check that `orders` is a `list`. Non-list input produces a cryptic `TypeError` with no helpful message. |
| **Fix Direction**   | `if not isinstance(orders, list): raise ValueError("orders must be a list.")` |
| **Reference**       | `fixed_order_processor.py` line 98. |

---

### L-04 — `"orderId"` camelCase key in Python dict

| Field               | Value |
|---------------------|-------|
| **Severity**        | Low |
| **Category**        | PEP 8 & Style |
| **Location**        | `process_orders`, line 59 |
| **Description**     | Dictionary keys in Python code should use `snake_case` per PEP 8. `"orderId"` is camelCase. (Functional impact covered under H-08.) |
| **Fix Direction**   | Use `"order_id"` consistently. |
| **Reference**       | PEP 8 — Naming Conventions. |

---

## Coverage Summary

| Analysis Dimension        | Findings | Severity Breakdown                           |
|---------------------------|----------|----------------------------------------------|
| OOP & Design (SRP)        | 2        | 0 Critical, 0 High, 1 Medium, 1 Low          |
| PEP 8 & Style             | 3        | 0 Critical, 0 High, 1 Medium, 2 Low          |
| Type Safety               | 2        | 0 Critical, 0 High, 1 Medium, 1 Low          |
| Docstring Coverage        | 1        | 0 Critical, 0 High, 1 Medium, 0 Low          |
| Logical Correctness       | 5        | 3 Critical, 2 High, 0 Medium, 0 Low          |
| Robustness & Validation   | 5        | 0 Critical, 3 High, 0 Medium, 1 Low          |
| Error Handling            | 1        | 1 Critical, 0 High, 0 Medium, 0 Low          |
| Security & Data Integrity | 2        | 1 Critical, 1 High, 0 Medium, 0 Low          |
| Performance               | 1        | 0 Critical, 0 High, 1 Medium, 0 Low          |
| Schema Stability          | 1        | 0 Critical, 2 High, 0 Medium, 0 Low          |
| **TOTAL**                 | **23**   | **Critical: 5, High: 9, Medium: 5, Low: 4**  |

---

## Risk Register

| Risk                                                   | Likelihood | Impact | Mitigation Required                                           |
|--------------------------------------------------------|------------|--------|---------------------------------------------------------------|
| Zero orders processed correctly in production          | Certain    | High   | Fix C-01 (IndexError) and C-05 (broad except) immediately     |
| Enterprise customers over-billed by 8%                 | High       | High   | Fix C-02 (discount rate mapping) before any live traffic      |
| Coupon saves $20 instead of $200 on a $1k order        | High       | High   | Fix C-03 (coupon as percentage) before coupon feature is live |
| Float rounding errors on all financial totals          | Certain    | High   | Fix C-04 (switch to Decimal) before any billing integration   |
| Duplicate orders silently double-billed                | High       | High   | Fix H-01 (duplicate detection no-op)                          |
| Negative order totals entering downstream systems      | Medium     | High   | Fix H-06 (floor guard) alongside C-03                         |
| All API consumers broken by schema typo "totl"         | Certain    | High   | Fix H-07 immediately — no workaround for callers              |
| mypy CI gate failing on every push                     | Certain    | Medium | Fix M-02 (add type hints)                                     |

---

## Approval Gate

**The Planning Agent MUST NOT start until this section shows APPROVED.**

> Architecture review is complete. All 23 findings are documented above across
> 5 Critical, 9 High, 5 Medium, and 4 Low severity levels.
>
> To proceed to fix planning, review the findings table and reply:
> - **APPROVE** — findings are accepted; Planning Agent may begin
> - **REJECT: <reason>** — findings need revision before planning proceeds

**Current Status:** ✅ APPROVED — 2026-04-08
