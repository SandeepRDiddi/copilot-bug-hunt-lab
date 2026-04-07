# Copilot Bug Hunt Lab

Hands-on lab for teaching:
- Debugging AI-generated Python code with GitHub Copilot
- Finding logical issues and edge cases
- Refactoring legacy code safely
- Improving performance and readability
- Automating quality checks with GitHub Actions

## Project Structure

- `buggy_order_processor.py` - intentionally buggy module for exercises
- `fixed_order_processor.py` - enterprise-grade fixed reference
- `tests/test_order_processor.py` - regression and edge-case tests
- `prompts/enterprise_bug_audit_prompt.md` - reusable Copilot prompt
- `.github/copilot-instructions.md` - repo-specific Copilot guidance
- `.github/workflows/python-quality.yml` - CI quality gate
- `teaching/CLASS_PLAN.md` - step-by-step classroom plan

## Local Setup

1. Create virtual environment:
   - `python3 -m venv .venv`
   - `source .venv/bin/activate`
2. Install tooling:
   - `pip install --upgrade pip`
   - `pip install pytest ruff mypy`
3. Run checks:
   - `ruff check .`
   - `mypy .`
   - `pytest -q`

## Suggested Lab Flow

1. Start from `buggy_order_processor.py`.
2. Ask Copilot to produce findings using prompt in `prompts/enterprise_bug_audit_prompt.md`.
3. Add failing tests first.
4. Fix in small commits.
5. Validate with lint, type-check, tests.
6. Compare against `fixed_order_processor.py`.
