# Bug Catalog — legacy_inventory_system.py
> Teacher's answer key. Do NOT share with students before the exercise.

## CRITICAL (Security / Data Loss)

| # | Location | Bug | Fix |
|---|----------|-----|-----|
| C1 | `create_user()` | **SQL Injection** via `%s` string formatting in INSERT | Use `?` parameterized queries |
| C2 | `login()` | **SQL Injection** in SELECT with username/password interpolation | Parameterized query |
| C3 | `admin_reset_all_passwords()` | **SQL Injection** in UPDATE + **no auth check** + no WHERE clause — resets *everyone* | Auth gate + parameterized query + WHERE clause |
| C4 | `hash_password()` | **MD5 used for passwords** — broken, rainbow-table crackable | Use `bcrypt` or `argon2` |
| C5 | `SMTP_PASS`, `ADMIN_PASS`, `SECRET_KEY` | **Hardcoded credentials** in source code | Use environment variables / secrets manager |
| C6 | `change_password()` | **Old password never verified** before overwriting | Verify `old_pw` first |

---

## HIGH (Correctness / Data Integrity)

| # | Location | Bug | Fix |
|---|----------|-----|-----|
| H1 | `log()` | `audit_log.append(ts, msg)` — `append()` takes 1 arg, crashes at runtime | `audit_log.append((ts, msg))` |
| H2 | `place_order()` | `log("Order placed: " + oid)` — `oid` is `int`, `TypeError` at runtime | `str(oid)` |
| H3 | `delete_user()` | `cur.execute(..., user_id)` — must be a tuple `(user_id,)` | `(user_id,)` |
| H4 | `add_product()` | INSERT missing `category` arg — `sqlite3.ProgrammingError` | Add `category` to values tuple |
| H5 | `place_order()` | **Race condition** — no lock around stock check + decrement | Wrap with `LOCK` or DB transaction |
| H6 | `calculate_total()` | `DISCOUNT` applied as flat **$10 off** not percent; can produce negative totals | Compute `total * (DISCOUNT / 100)` |
| H7 | `process_refund()` | Condition inverted — refunds succeed only on non-completed orders | Flip to `if o["status"] == "completed"` |

---

## MEDIUM (Logic / Business Rules)

| # | Location | Bug | Fix |
|---|----------|-----|-----|
| M1 | `add_product()` / `place_order()` | ID generated as `len(dict)+1` — **collision after any deletion** | Use `max(keys)+1` or DB `AUTOINCREMENT` |
| M2 | `get_low_stock()` | Items with `qty==0` appended **twice** (satisfies both `< 10` and `== 0`) | Remove the `== 0` branch |
| M3 | `top_selling_products()` | Sorted **ascending** — returns worst sellers, not top sellers | `reverse=True` |
| M4 | `generate_sales_report()` | `start_date`/`end_date` params **completely ignored** | Parse and filter `created_at` |
| M5 | `generate_sales_report()` | Counts **pending** orders as revenue | Filter to `completed` only |
| M6 | `cancel_order()` | Can cancel **already-shipped/completed** orders with no guard | Check status before cancelling |
| M7 | `update_stock()` | Accepts **negative quantities** — no validation | `if quantity < 0: raise ValueError` |
| M8 | `login()` | Token is `SECRET_KEY + username` — **not a real auth token**, no expiry | Use `secrets.token_hex` or JWT |

---

## LOW (Quality / Reliability)

| # | Location | Bug | Fix |
|---|----------|-----|-----|
| L1 | `get_config()` | File handle **never closed** (commented-out close) | Use `with open(...)` |
| L2 | `export_report_csv()` | File opened in **append mode**, **never closed** — grows forever | `with open(filename, "w")` |
| L3 | `delete_product()` | Deletes from memory dict but **not from DB** | Add `DELETE FROM products WHERE id=?` |
| L4 | `purge_old_orders()` | Purges from memory **only**, not DB | Add `DELETE FROM orders WHERE ...` |
| L5 | `get_product()` | Cache **never expires** — stale prices forever | Add TTL or invalidate on `update_stock` |
| L6 | `get_orders_for_user()` | Returns **in-memory list only** — DB orders lost on restart | Query DB instead |
| L7 | `get_order_status()` | Returns string `"not found"` — **indistinguishable from a real status** | Return `None` and let caller handle |
| L8 | `admin_get_all_users()` | Returns **password hashes** to caller — information leak | Strip password field |
| L9 | `send_order_email()` | Called **synchronously inside order transaction** — slow + crash risk | Use a task queue (Celery, etc.) |
| L10 | `send_low_stock_alert()` | Calls **wrong function** (`send_order_email`) with dummy args | Implement dedicated alert function |
| L11 | `apply_bulk_discount()` | Discount **stacks** on repeated calls (no DB sync, no idempotency) | Store original price or sync to DB |
| L12 | `search_products()` | **Case-sensitive** search on 500k products with O(n) scan | Normalize case; add DB index + `LIKE` |
| L13 | `get_user_by_id()` | Falls through to a raw `%d` SQL format string — **minor injection surface** | Parameterized query |

---

## Anti-Patterns (Refactoring Targets)

- **Global mutable state**: `conn`, `users`, `orders`, `inventory`, `_cache`, `audit_log` — no encapsulation
- **God module**: auth + inventory + orders + reporting + email + admin all in one file
- **No type hints** anywhere
- **Bare `except: pass`** swallows all exceptions silently
- **Magic numbers/strings**: `0.08`, `10`, `0.5`, `"not found"`, `9999`
- **Mixed DB + in-memory state**: restarts wipe in-memory state silently
- **No input validation** at any public function boundary
- **Dead code**: commented-out `.close()` calls, `# TODO` notes never resolved

---

## Suggested Refactoring Order for Class

1. **Round 1 — Critical security** (C1–C6): parameterized SQL, bcrypt, env vars
2. **Round 2 — Runtime crashes** (H1–H4): fix argument errors that break immediately
3. **Round 3 — Business logic** (H5–H7, M1–M8): race condition, discount, refund, IDs
4. **Round 4 — Reliability** (L1–L13): file handles, cache, DB sync
5. **Round 5 — Architecture**: split into `auth.py`, `inventory.py`, `orders.py`, `reports.py`; add dataclasses + type hints
