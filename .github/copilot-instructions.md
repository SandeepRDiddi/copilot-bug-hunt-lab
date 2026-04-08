# Copilot Instructions

## Commands

```bash
# Lint
ruff check .

# Type-check
mypy .

# Full test suite
pytest -q

# Single test
pytest tests/test_order_processor.py::test_calculate_discounted_total_happy_path -v

# All checks (mirrors CI)
ruff check . && mypy . && pytest -q
```

## Architecture

This is a teaching lab centred on two versions of the same module:

- **`buggy_order_processor.py`** — intentionally broken reference; do NOT fix it (it exists to be analysed and used for exercises).
- **`fixed_order_processor.py`** — the production-grade reference implementation; all tests (`tests/test_order_processor.py`) import from here.

The CI workflow (`.github/workflows/python-quality.yml`) runs ruff → mypy → pytest on every PR and push to `main`.

## Key Conventions

**Money handling**
- Always use `Decimal` with `ROUND_HALF_UP`; use the `TWO_PLACES = Decimal("0.01")` constant.
- Convert floats/strings via `_to_decimal(value)` (i.e. `Decimal(str(value))`) to avoid float precision loss.

**Discount logic**
- `DISCOUNT_BY_TIER` maps customer type → discount *rate* (e.g. `"enterprise": Decimal("0.10")` means 10% off).
- Coupon discount is *multiplicative* (`total *= 1 - percent/100`), not a flat subtraction.
- Expired coupons are silently skipped; invalid coupon structure raises `ValueError`.

**Return schema — never change without updating tests**
- `process_orders` returns `list[dict[str, str]]` with keys `order_id` and `total` (total as `"1080.00"` formatted string).
- `OrderResult` dataclass (`frozen=True`) is available for typed internal use.

**Validation & error handling**
- Raise `ValueError` with an explicit message for every invalid input; never use broad `except Exception`.
- Validate items in `_validate_item`: check required keys, non-empty name, non-negative price and qty.
- Duplicate `order_id` values must raise `ValueError`, not silently pass.

**Algorithmic choices**
- Use `set[str]` (O(1)) for duplicate-order detection, not a list (O(n²)).

**Testing**
- Tests live in `tests/test_order_processor.py` and import from `fixed_order_processor`.
- Every bug fix requires at least one regression test.
- Use `pytest.mark.parametrize` for boundary tests (e.g. coupon percent 0–100).

**Code style**
- Line length 100 (`pyproject.toml`), target Python 3.11.
- All public functions must have type hints (`mypy` enforces `disallow_untyped_defs`).
- Prioritize correctness over brevity; explain edge-case handling in short bullets.
- For refactors: write failing tests first, then patch the implementation.
