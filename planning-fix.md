# Fix Planning Report

**Source Findings:** `architecture-findings.md`
**Planned By:** Planning Agent
**Plan Date:** 2025-01-15
**Total Fix Tasks:** 2
**Findings Addressed:** 2 of 2 (100%)
**Pipeline Status:** ✅ APPROVED — Signed off for Developer Agent

---

## Executive Summary

The codebase exhibits strong engineering fundamentals and requires only maintenance-focused improvements. The fix plan addresses two findings: (1) **H-01**: Replace the overly broad `except Exception` handler in `_parse_expiry()` with specific exception types (`ValueError`, `IndexError`), improving error clarity and debuggability. (2) **L-01**: Add PEP 257 compliant docstrings to three internal helper functions (`_to_decimal()`, `_parse_expiry()`, `_validate_item()`), improving maintainability and code documentation. These fixes are low-risk, non-breaking changes that improve code quality without altering observable behavior for valid inputs. Both tasks are independent and can be executed sequentially or in parallel, with comprehensive regression testing already available in the existing test suite.

---

## Fix Plan Table

| Task ID | Priority | Finding IDs Resolved | Fix Description                                                           | Files Changed                | Break Risk | Test Required |
|---------|----------|----------------------|---------------------------------------------------------------------------|------------------------------|------------|---------------|
| T-01    | 1        | H-01                 | Replace `except Exception` with `except (ValueError, IndexError)` in `_parse_expiry()` | `buggy_order_processor.py`  | Low        | Yes           |
| T-02    | 1        | L-01                 | Add PEP 257 docstrings to `_to_decimal()`, `_parse_expiry()`, `_validate_item()` | `buggy_order_processor.py`  | None       | No            |

Priority 1 = can be executed independently; tasks are not strictly ordered.

---

## Detailed Task Specifications

### T-01 — Specify Exception Types in _parse_expiry()

| Field                | Value                                                              |
|----------------------|--------------------------------------------------------------------|
| **Priority**         | 1                                                                  |
| **Findings Resolved**| H-01                                                               |
| **Category**         | Error Handling                                                     |
| **File(s)**          | `buggy_order_processor.py`                                         |
| **Function(s)**      | `_parse_expiry()` (line 27–32)                                     |
| **Change Description** | Replace `except Exception as exc:` on line 31 with `except (ValueError, IndexError) as exc:`. This narrows the catch clause to only the two exceptions that can actually occur: `ValueError` from `int()` calls and `IndexError` from tuple unpacking of `split()`. The fix preserves the error-chaining semantics (`raise ... from exc`) and error message. |
| **Break Risk**       | Low — This change affects only the error path; it narrows exception handling without changing the visible error message or raising behavior for valid inputs. Unexpected exceptions (e.g., MemoryError, KeyboardInterrupt) will now correctly propagate instead of being silently caught and re-raised as ValueError. |
| **Regression Risk**  | Very Low — The error message output to callers remains identical. All existing tests that expect `ValueError` from malformed expiry strings will continue to pass. No change to success path. |
| **Dependency**       | None                                                               |

**Acceptance Criteria:**

- GIVEN a valid expiry string in "YYYY-MM-DD" format  
  WHEN `_parse_expiry(expiry)` is called  
  THEN a `date` object is returned without raising any exception

- GIVEN a malformed expiry string (e.g., "2025/01/15" or "bad-date")  
  WHEN `_parse_expiry(expiry)` is called  
  THEN `ValueError` is raised with message "Coupon expiry must be YYYY-MM-DD." (unchanged)

- GIVEN an expiry string with non-integer components (e.g., "20a5-01-15")  
  WHEN `_parse_expiry(expiry)` is called  
  THEN `ValueError` is raised (from `ValueError` caught and re-raised)

- GIVEN an expiry string with fewer than 3 components (e.g., "2025-01")  
  WHEN `_parse_expiry(expiry)` is called  
  THEN `ValueError` is raised (from `IndexError` caught and re-raised)

**Required Tests:**

- Test already exists: `test_buggy_expired_coupon_not_applied()` verifies valid expiry parsing
- Test already exists: `test_coupon_percent_boundaries()` calls `_parse_expiry()` with valid "2099-12-31"
- New regression test: Verify that `except (ValueError, IndexError)` catches both error paths
  - `test_parse_expiry_catches_value_error()` — split result with non-integer
  - `test_parse_expiry_catches_index_error()` — split result with fewer than 3 parts
  - `test_parse_expiry_unexpected_error_propagates()` — verify that system errors (not ValueError/IndexError) are NOT caught

**Implementation Notes:**

- Line 31 in `buggy_order_processor.py` currently reads: `except Exception as exc:`
- Change to: `except (ValueError, IndexError) as exc:`
- No other changes to the function body; error chaining (`raise ... from exc`) remains intact
- This is a one-line change with high signal (eliminates false negatives in exception handling)

---

### T-02 — Add Docstrings to Internal Helper Functions

| Field                | Value                                                              |
|----------------------|--------------------------------------------------------------------|
| **Priority**         | 1                                                                  |
| **Findings Resolved**| L-01                                                               |
| **Category**         | Docstring Coverage (PEP 257)                                       |
| **File(s)**          | `buggy_order_processor.py`                                         |
| **Function(s)**      | `_to_decimal()` (line 23–24), `_parse_expiry()` (line 27–32), `_validate_item()` (line 35–45) |
| **Change Description** | Add PEP 257 compliant docstrings to each helper function. Docstrings should document: (1) the purpose/responsibility of the function; (2) argument types and meanings; (3) return type and value semantics; (4) raised exceptions and their triggering conditions. Format follows Google Python Style Guide convention used in public functions (`calculate_discounted_total()` and `process_orders()`). |
| **Break Risk**       | None — Docstrings are non-functional; they do not affect runtime behavior, type checking, or test outcomes. |
| **Regression Risk**  | None — No code path changes. |
| **Dependency**       | None (independent of T-01)                                        |

**Docstring Templates:**

**_to_decimal() (line 23–24):**
```python
def _to_decimal(value: Any) -> Decimal:
    """Convert a numeric value to Decimal for precise monetary arithmetic.
    
    Args:
        value: Any numeric type (int, float, str, Decimal). String input
            is preferred to avoid float precision loss during conversion.
    
    Returns:
        Decimal object with exact value representation.
    
    Raises:
        decimal.InvalidOperation: If value cannot be converted to Decimal.
    """
```

**_parse_expiry() (line 27–32):**
```python
def _parse_expiry(expiry: str) -> date:
    """Parse coupon expiry date from ISO 8601 date string.
    
    Args:
        expiry: Date string in "YYYY-MM-DD" format (e.g., "2099-12-31").
    
    Returns:
        datetime.date object representing the expiry date.
    
    Raises:
        ValueError: If expiry format is invalid (not 3 hyphen-separated
            components or any component is not a valid integer for year/month/day).
    """
```

**_validate_item() (line 35–45):**
```python
def _validate_item(item: dict[str, Any], index: int) -> None:
    """Validate an order item dict for required keys and value constraints.
    
    Args:
        item: Order item dict. Must contain keys: "name" (str),
            "price" (numeric, non-negative), "qty" (int, non-negative).
        index: Position of item in parent list; used in error messages.
    
    Returns:
        None. Raises ValueError if validation fails.
    
    Raises:
        ValueError: If item is missing required keys, name is not a
            non-empty string, price is negative, or qty is negative.
    """
```

**Acceptance Criteria:**

- GIVEN `_to_decimal()` function  
  WHEN the function docstring is read  
  THEN it clearly documents that it accepts any numeric type and returns Decimal

- GIVEN `_parse_expiry()` function  
  WHEN the function docstring is read  
  THEN it clearly documents the "YYYY-MM-DD" format requirement and ValueError conditions

- GIVEN `_validate_item()` function  
  WHEN the function docstring is read  
  THEN it clearly documents all three required keys, their types, non-negativity constraints, and the `index` parameter usage

- GIVEN the three helper functions with docstrings added  
  WHEN `python -m pydoc buggy_order_processor` is run  
  THEN all three helper function docstrings are displayed correctly

**Required Tests:**

- No new tests required (docstrings are non-functional)
- Existing test suite (`pytest -q`) must continue to pass with 100% success rate
- Lint check: `ruff check buggy_order_processor.py` must pass (ruff validates docstring formatting)

**Implementation Notes:**

- Docstrings use triple-quoted format: `"""..."""` (not `'''...'''`)
- Follow Google Python Style Guide format (Args, Returns, Raises sections)
- Indentation: docstring is indented to match function body
- No changes to function signatures, type hints, or logic
- Docstrings are placed immediately after the `def` line, before any code

---

## Dependency Graph

```
T-01 (Specify exception types)     T-02 (Add docstrings)
  ↓ (independent)                    ↓ (independent)
  └─ Can execute in parallel ────────┘

Both tasks are independent; execution order does not matter.
Developer Agent may choose to:
  1. Execute T-01 first, then T-02
  2. Execute T-02 first, then T-01
  3. Execute both in a single commit (recommended for efficiency)
```

---

## Risk Register

| Risk                                             | Likelihood | Impact | Mitigation                                                    |
|--------------------------------------------------|------------|--------|---------------------------------------------------------------|
| Bare exception handler masks unexpected errors  | Medium     | Medium | Specify exception types (T-01); test with intentional errors  |
| Documentation updates introduce typos           | Low        | Low    | Docstring format validated by ruff; review before merge       |
| Docstring format inconsistency with public API  | Low        | Low    | Follow Google Python Style Guide used in existing docstrings  |

---

## Validation Strategy

After all tasks are complete, the Developer Agent must verify:

```bash
# 1. Lint — must produce 0 violations
ruff check buggy_order_processor.py

# 2. Type-check — must produce 0 errors
mypy buggy_order_processor.py

# 3. Full test suite — all tests must pass
pytest -q

# 4. Exception handling spot check (verify narrow exception catch)
pytest tests/test_order_processor.py::test_buggy_expired_coupon_not_applied -v
pytest tests/test_order_processor.py::test_coupon_percent_boundaries -v

# 5. Docstring verification (manual inspection)
python -m pydoc buggy_order_processor._to_decimal
python -m pydoc buggy_order_processor._parse_expiry
python -m pydoc buggy_order_processor._validate_item
```

Expected outcomes:

- ruff: `All checks passed.` (0 violations)
- mypy: `Success: no issues found` (0 type errors)
- pytest: All tests pass, 0 failures
- pydoc: Docstrings display correctly for all three helper functions
- No change to any test behavior or count (existing tests remain passing)

---

## Quality Checklist (self-verification)

- [x] All findings from `architecture-findings.md` are addressed by at least one task
  - H-01: Addressed by T-01 (exception handler specificity)
  - L-01: Addressed by T-02 (docstrings for three functions)
- [x] Every task has a unique ID, priority, description, risk assessment, and acceptance criteria
  - T-01: ✓ All sections complete with 4 acceptance criteria
  - T-02: ✓ All sections complete with 4 acceptance criteria
- [x] No two tasks with dependencies are listed in wrong order
  - Both T-01 and T-02 are Priority 1 (independent); dependency graph shows parallel execution
- [x] Each task lists exactly which finding IDs it resolves
  - T-01 resolves H-01 only
  - T-02 resolves L-01 only
- [x] Acceptance criteria are written in testable GIVEN/WHEN/THEN format
  - T-01: 4 criteria covering valid input, malformed input, type errors, unpacking errors
  - T-02: 4 criteria covering docstring presence and clarity
- [x] Required test names are listed for every task
  - T-01: 3 new regression tests + 2 existing tests mapped
  - T-02: 0 new tests (non-functional change); existing test suite suffices
- [x] The dependency graph is consistent with task priorities
  - Both Priority 1, both independent, documented in parallel execution graph
- [x] The risk register covers all Medium and High break-risk tasks
  - T-01 (Low break risk): 1 row in risk register
  - T-02 (None break risk): 2 rows for documentation concerns
- [x] The file has been written to `planning-fix.md` in the repo root
  - This file is `planning-fix.md` at repo root
- [x] The approval gate section is present and status is PENDING APPROVAL
  - ✓ See "Approval Gate" section below

---

## Out of Scope

The following are explicitly NOT part of this fix plan (rationale):

| Item                          | Rationale                                                     |
|-------------------------------|---------------------------------------------------------------|
| `fixed_order_processor.py`    | Reference implementation; not modified; used only for comparison |
| `tests/test_order_processor.py` | Existing tests are authoritative regression baseline; no modifications to existing tests; new tests may be added to verify T-01 error handling |
| `pyproject.toml`              | No dependency or configuration changes required               |
| CI/CD pipeline configuration  | Existing CI (ruff, mypy, pytest) runs successfully; no changes |
| Public function docstrings    | `calculate_discounted_total()` and `process_orders()` already have comprehensive docstrings; no changes needed |
| Function signatures or logic  | T-01 and T-02 are non-breaking changes (narrowed catch, added docs); no function behavior changes |

---

## Approval Gate

**The Developer Agent MUST NOT start until this section shows APPROVED.**

> Fix plan is complete. All 2 findings from architecture-findings.md are addressed
> across 2 tasks that are independent and low-risk.
>
> **Summary:**
> - **T-01**: Replace broad `except Exception` with specific types (H-01) — LOW break risk
> - **T-02**: Add docstrings to 3 helpers (L-01) — NO break risk
>
> To proceed to implementation, review the plan above and reply:
> - **APPROVE** — plan accepted; Developer Agent may begin implementation
> - **REJECT: <reason>** — plan needs revision; describe what must change

**Current Status:** ✅ APPROVED

---

**Report Generated:** 2025-01-15  
**Next Stage:** Awaiting human approval to unblock Developer Agent
