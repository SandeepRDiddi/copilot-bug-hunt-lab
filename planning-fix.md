# Fix Planning Report

**Source Findings:** `architecture-findings.md`
**Planned By:** Planning Agent
**Plan Date:** 2026-04-09
**Total Fix Tasks:** 5
**Findings Addressed:** 5 of 5 (100%)
**Pipeline Status:** ⏸️ AWAITING APPROVAL — Developer Agent must not start until APPROVED

---

## Executive Summary

The fix strategy prioritizes **critical correctness first**, then **type safety**, and finally **style cleanup**. The coupon expiry bug (C-01) is a revenue-impacting defect that must be fixed immediately and independently — no other changes depend on it, but all calculation logic depends on it being correct. The `OrderResult` dataclass integration (H-02) is the highest-leverage fix: it resolves both the schema instability (H-01) and dead code (M-02) in a single refactoring. Blank line cleanup (M-01) is purely cosmetic and can be done last. All fixes are low-risk because:

1. **C-01** is a one-operator change (>= → >), protected by coupon-expiry boundary tests
2. **H-02** and **H-01** are addressed by returning `list[OrderResult]` instead of `list[dict[str, str]]` — the schema is identical, only the type is strengthened
3. **M-01** has zero business impact

The dependency graph is linear with no blocking chains: all tasks can theoretically run in parallel, but are sequenced for clarity.

---

## Fix Plan Table

| Task ID | Priority | Finding IDs Resolved | Fix Description | Files Changed | Break Risk | Test Required |
|---------|----------|----------------------|-----------------|--|------------|---------------|
| T-01 | 1 | C-01 | Fix coupon expiry comparison operator: `>=` → `>` on line 97 | `buggy_order_processor.py` | Low | Yes |
| T-02 | 2 | H-02, H-01, M-02 | Return `list[OrderResult]` instead of `list[dict[str, str]]`; remove dead code | `buggy_order_processor.py` | Medium | Yes |
| T-03 | 3 | M-01 | Remove one blank line between `_validate_item` and `calculate_discounted_total` | `buggy_order_processor.py` | None | No |

---

## Detailed Task Specifications

### T-01 — Fix Coupon Expiry Operator

| Field | Value |
|-------|-------|
| **Priority** | 1 |
| **Findings Resolved** | C-01 |
| **Category** | Logical Correctness |
| **File(s)** | `buggy_order_processor.py` |
| **Function(s)** | `calculate_discounted_total()` |
| **Line Number** | 97 |
| **Change Description** | Change `if expiry >= date.today():` to `if expiry > date.today():`. Standard business semantics: a coupon that "expires on date X" means it is **not valid on date X**. The current `>=` applies the coupon on its expiry date, which is incorrect. This is a one-character fix (remove the `=`). |
| **Break Risk** | **Low**. The fix corrects an off-by-one bug. No valid use case relies on applying expired coupons — all existing tests should expect coupons to expire **before** their expiry date, not on it. |
| **Regression Risk** | If any test expects a coupon to be valid ON its expiry date, that test is wrong and should fail—which is good, because it tests the bug, not the correct behavior. Review test results carefully. |
| **Dependency** | None — this is an independent calculation fix. |

**Acceptance Criteria:**

- GIVEN a coupon with `expires_at: "2026-04-09"` (today's date)
  WHEN `calculate_discounted_total()` is called with that coupon on 2026-04-09
  THEN the coupon is **not applied** (no discount taken)

- GIVEN a coupon with `expires_at: "2026-04-10"` (tomorrow)
  WHEN `calculate_discounted_total()` is called with that coupon on 2026-04-09
  THEN the coupon is **applied** (discount is taken)

- GIVEN a coupon with `expires_at: "2026-04-08"` (yesterday)
  WHEN `calculate_discounted_total()` is called with that coupon on 2026-04-09
  THEN the coupon is **not applied** (no discount taken)

**Required Tests:**

- Verify existing tests still pass OR correctly identify tests that relied on the buggy behavior
- If no existing test covers "coupon expires today", add: `test_expired_coupon_not_applied_on_expiry_date`

---

### T-02 — Return `OrderResult` Dataclass (Fix H-02 + H-01 + M-02)

| Field | Value |
|-------|-------|
| **Priority** | 2 |
| **Findings Resolved** | H-02, H-01, M-02 |
| **Category** | Type Safety & Schema Stability |
| **File(s)** | `buggy_order_processor.py` |
| **Function(s)** | `process_orders()` |
| **Lines** | 105, 123, 142 |
| **Change Description** | Three coordinated changes: (1) Update return type from `list[dict[str, str]]` to `list[OrderResult]`. (2) On line 142, replace `results.append({"order_id": order_id, "total": f"{total:.2f}"})` with `results.append(OrderResult(order_id=order_id, total=total))` where `total` is **Decimal, not string**. (3) Update the function's docstring to reflect that returns `list[OrderResult]`, where each `OrderResult.total` is a `Decimal` with 2 decimal places. This automatically eliminates M-02 (dead code) by actually using `OrderResult`. |
| **Break Risk** | **Medium**. The **external schema is identical** (callers still see the same data), but the **type signature changes**. This is safe if: (1) Callers iterate over results and access `.order_id` and `.total` by attribute (which works the same for dataclass and dict). (2) Callers that serialize results to JSON will not see a difference (dataclasses serialize the same as dicts). (3) Type-checking callers will now get stronger guarantees. However, if any caller does duck-typing or relies on dict-specific methods (e.g., `.keys()`, `.items()`), that code will break. Such usage is non-standard and should be fixed. **This is why the risk is Medium, not Low.** |
| **Regression Risk** | If a caller calls `.get()`, `.keys()`, `.items()`, or other dict methods on result items, those will fail with `AttributeError`. These are programming errors and should surface in tests. No hidden breakage. |
| **Dependency** | Must follow T-01 (coupon expiry fix must be correct before we freeze the schema in `OrderResult`). |

**Acceptance Criteria:**

- GIVEN an order with items and a coupon
  WHEN `process_orders()` is called
  THEN each result is an `OrderResult` instance (not a dict)

- GIVEN a result from `process_orders()`
  WHEN accessing result`.order_id`
  THEN the value is the correct string order ID

- GIVEN a result from `process_orders()`
  WHEN accessing result`.total`
  THEN the value is a `Decimal` with exactly 2 decimal places (e.g., `Decimal("1080.50")`)

- GIVEN multiple results from `process_orders()`
  WHEN serializing to JSON (e.g., via `json.dumps()` with a custom encoder)
  THEN each result encodes to `{"order_id": "...", "total": "..."}`

- GIVEN the module
  WHEN scanning for `OrderResult` usage
  THEN it is instantiated and returned (dead code eliminated)

**Required Tests:**

- `test_process_orders_returns_orderresult_instances`
- `test_orderresult_total_is_decimal`
- `test_orderresult_fields_correct`
- Verify JSON serialization (if applicable to calling code)

---

### T-03 — Fix PEP 8 Blank Line Violation

| Field | Value |
|-------|-------|
| **Priority** | 3 |
| **Findings Resolved** | M-01 |
| **Category** | Code Style (PEP 8) |
| **File(s)** | `buggy_order_processor.py` |
| **Lines** | 46–50 |
| **Change Description** | Between the end of `_validate_item()` (line 46) and start of `calculate_discounted_total()` (line 50), there are currently 3 blank lines (lines 47, 48, 49). PEP 8 § 302 mandates exactly 2 blank lines between top-level function definitions. Delete one blank line so only two remain. |
| **Break Risk** | **None**. This is purely whitespace and has zero impact on functionality or types. |
| **Regression Risk** | None. |
| **Dependency** | None — can be done independently. |

**Acceptance Criteria:**

- GIVEN the source file
  WHEN counting blank lines between `_validate_item()` and `calculate_discounted_total()`
  THEN exactly 2 blank lines are present

- GIVEN ruff linting
  WHEN run on `buggy_order_processor.py`
  THEN no E302 violations are reported (PEP 8 blank line rule)

**Required Tests:**

- Run `ruff check buggy_order_processor.py` — must pass
- No new pytest tests needed

---

## Dependency Graph

```
T-01 (coupon expiry fix — independent)
  ├─ T-02 (return OrderResult — depends on T-01 being correct)
  └─ T-03 (blank line cleanup — independent)

Execution order: T-01 → T-02 → T-03 (sequential)
Blocking order: T-01 must complete before T-02; T-02 must complete before T-03
```

In detail:
- **T-01 must complete first** because the coupon expiry logic is the foundation. If T-01 is wrong, the schema in `OrderResult` will return incorrect values.
- **T-02 depends on T-01** being correct (though the actual code in T-02 doesn't call T-01; they are separate functions).
- **T-03 is independent** but sequenced last because it's low-risk and can be done when everything else is done.

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|-----------|
| T-01: Existing test relies on buggy `>=` behavior | Low | Medium | Review all coupon-expiry tests; any test expecting a coupon valid on its expiry date is testing the bug, not correct behavior. That test should fail and be fixed. |
| T-02: Caller code uses dict methods on results (`.keys()`, `.get()`, etc.) | Low | High | This would be non-standard usage. Any such code will fail at runtime with `AttributeError`. Tests should catch it immediately. Add a test that tries typical dict operations and confirms they fail as expected (or use hasattr to guard). |
| T-02: JSON serialization changes | Very Low | Low | Python's `json.dumps()` on a dataclass requires a custom encoder (`dataclasses.asdict()` or `JSONEncoder`). If callers already use a custom encoder for `OrderResult`, no change. If they relied on implicit dict encoding, they must migrate to `dataclasses.asdict(result)`. This is a rare edge case—most code uses a web framework that handles it. |
| T-03: Blank line change breaks something | None | None | Whitespace changes have zero impact. This is pure style. No risk. |

---

## Validation Strategy

After all three tasks are complete, the Developer Agent must verify:

```bash
# 1. Lint — must produce 0 violations
ruff check buggy_order_processor.py

# 2. Type-check — must produce 0 errors
mypy buggy_order_processor.py

# 3. Full test suite — all tests must pass
pytest -xvs

# 4. Spot checks for the three fixes
pytest tests/test_order_processor.py::test_expired_coupon_not_applied_on_expiry_date -v
pytest tests/test_order_processor.py::test_process_orders_returns_orderresult_instances -v
pytest tests/test_order_processor.py::test_orderresult_total_is_decimal -v
```

**Expected outcomes:**
- `ruff check`: All checks passed (no E302 blank line violations)
- `mypy`: Success: no issues found
- `pytest`: All tests pass, 0 failures (baseline + new regression tests)

---

## Out of Scope

The following are explicitly **NOT** part of this fix plan:

| Item | Reason |
|------|--------|
| `fixed_order_processor.py` | This is the reference solution; do not modify it. Compare against it for correctness verification only. |
| `tests/test_order_processor.py` (existing tests) | Existing tests must continue to pass. New regression tests may be added. Do not modify passing tests unless they test the C-01 bug (in which case, fix them to test correct behavior). |
| `pyproject.toml` | No dependency changes required. |
| CI/CD configuration (`.github/workflows/*`) | No workflow changes needed. Existing CI should pass. |

---

## Task Execution Summary

| Task | Lines Changed | Risk Level | Tests Added | Complexity |
|------|--|--|--|--|
| T-01 | 1 (line 97: `>=` → `>`) | Low | 1–2 | Trivial |
| T-02 | 4 (type annotation, return statement, docstring update) | Medium | 3–4 | Low |
| T-03 | 1 (delete blank line) | None | 0 | Trivial |
| **TOTAL** | **~6** | **Low–Medium** | **4–6** | **Low** |

---

## Approval Gate

**The Developer Agent MUST NOT start until this section shows APPROVED.**

> Fix plan is complete. All 5 findings from architecture-findings.md are addressed across 3 tasks in dependency order.
>
> To proceed to implementation, review the plan above and reply:
> - **APPROVE** — plan accepted; Developer Agent may begin implementation
> - **REJECT: <reason>** — plan needs revision; describe what must change

**Current Status:** ⏸️ PENDING APPROVAL

