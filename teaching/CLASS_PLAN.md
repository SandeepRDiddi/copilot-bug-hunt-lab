# Classroom Guide: Copilot for Python Debugging

## Audience
- Intermediate Python developers
- Basic Git and unit testing familiarity

## Duration
- 90 minutes (can extend to 120 with group review)

## Learning Outcomes
By end of class, learners can:
1. Use Copilot to identify logical and edge-case bugs.
2. Convert bug reports into regression tests.
3. Refactor legacy code with safe, incremental changes.
4. Improve readability and performance without behavior regressions.
5. Automate quality gates using GitHub Actions.

## Pre-Class Checklist
1. Ensure each learner has:
   - GitHub account with Copilot access
   - Python 3.11+
   - Git installed
   - VS Code or Cursor with Copilot Chat enabled
2. Share this repository in advance.
3. Ask learners to clone and run baseline checks.

## Step-by-Step Class Agenda

### Step 1: Intro and Context (10 min)
1. Explain AI-generated code risks:
   - subtle logic bugs
   - missing validation
   - hidden performance issues
2. Show repository structure and objectives.

### Step 2: Reproduce Failure (10 min)
1. Open `buggy_order_processor.py`.
2. Run:
   - `python buggy_order_processor.py`
3. Ask students to note unexpected behavior.

### Step 3: Copilot Bug Audit Prompt (15 min)
1. Open Copilot Chat.
2. Paste prompt from `prompts/enterprise_bug_audit_prompt.md`.
3. Ask Copilot to return Findings Table only.
4. Discuss severity ranking as a group.

### Step 4: Write Tests Before Fixing (15 min)
1. Open `tests/test_order_processor.py`.
2. Add or modify tests to capture reported bugs.
3. Run:
   - `pytest -q`
4. Confirm failing tests represent real defects.

### Step 5: Incremental Refactor with Copilot (20 min)
1. Ask Copilot: "Patch only Critical and High issues first."
2. Apply changes to create stable schema, validation, and money handling.
3. Run:
   - `ruff check .`
   - `mypy .`
   - `pytest -q`
4. Commit each meaningful step:
   - `git add . && git commit -m "fix: validate orders and stabilize totals"`

### Step 6: Performance and Readability Pass (10 min)
1. Ask Copilot to identify O(n^2) patterns and simplify.
2. Replace list-based duplicate checks with set-based checks.
3. Confirm no behavior regressions in tests.

### Step 7: CI Automation (5 min)
1. Review `.github/workflows/python-quality.yml`.
2. Explain merge gate model: lint + type-check + tests required.
3. Demonstrate opening PR and checks status.

### Step 8: Wrap-up and Q&A (5 min)
1. Recap repeatable bug-fix loop.
2. Share prompt patterns for future projects.

## Teaching Tips
- Enforce "tests first" discipline before code fixes.
- Require explicit assumptions for ambiguous business rules.
- Reject broad exception swallowing in student submissions.
- Prefer several small commits over one large commit.
- Use pair reviews for Copilot-generated patches.

## Assessment Rubric (Quick)
- Correctness: bug fixed and tests pass
- Robustness: edge cases handled
- Maintainability: readable, typed, documented
- Automation: CI configured and passing
