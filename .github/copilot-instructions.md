# Copilot Instructions

- Prioritize correctness over brevity.
- Never add broad `except Exception` unless explicitly requested.
- Use `Decimal` for currency calculations.
- Add type hints for public functions.
- Keep return schemas stable and explicit.
- For refactors, generate tests first, then patch.
- Every bug fix must include at least one regression test.
- Explain edge-case handling in short bullets.
