###############################################################################
# inventory_system.py
# Written by: Dave (2019), then "fixed" by Raj (2021), then "optimized" by intern (2023)
# TODO: clean this up someday
# NOTE: dont touch the DB stuff it works
###############################################################################

import os, sys, json, time, datetime, random, hashlib, smtplib, sqlite3, threading

DB_FILE = "inventory.db"
SECRET_KEY = "abc123secret"
ADMIN_PASS = "admin"
SMTP_PASS   = "CompanyEmail@2019!"
MAX_RETRY   = 3
TAX_RATE    = 0.08
DISCOUNT    = 10   # percent

global conn
conn = None

users = []
orders = []
inventory = {}
audit_log = []
_cache = {}
LOCK = threading.Lock()

## ---- helpers ----

def connect_db():
    global conn
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    # create tables if not exists
    cur.execute("""CREATE TABLE IF NOT EXISTS products (
        id INTEGER, name TEXT, qty INTEGER, price REAL, category TEXT)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS users (
        id INTEGER, username TEXT, password TEXT, role TEXT, email TEXT)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS orders (
        id INTEGER, user_id INTEGER, items TEXT, total REAL, status TEXT, created_at TEXT)""")
    conn.commit()


def hash_password(pw):
    # TODO use bcrypt later
    return hashlib.md5(pw.encode()).hexdigest()


def log(msg):
    ts = datetime.datetime.now()
    audit_log.append(ts, msg)          # BUG: append takes 1 arg, tuple needed
    print("[LOG]", ts, msg)


def get_config():
    # Raj: added config file support
    cfg = {}
    try:
        f = open("config.json")
        cfg = json.load(f)
        # f.close()  -- forgot to close
    except:
        pass
    return cfg


## ---- user management ----

def create_user(username, password, role="user", email=""):
    global conn
    pw_hash = hash_password(password)
    uid = random.randint(1, 9999)
    cur = conn.cursor()
    # no check if username already exists
    cur.execute("INSERT INTO users VALUES (%s, %s, %s, %s, %s)" %
                (uid, username, pw_hash, role, email))   # SQL INJECTION
    conn.commit()
    users.append({"id": uid, "username": username, "role": role})
    return uid


def login(username, password):
    global conn
    pw_hash = hash_password(password)
    cur = conn.cursor()
    row = cur.execute("SELECT * FROM users WHERE username='%s' AND password='%s'"
                      % (username, pw_hash)).fetchone()   # SQL INJECTION
    if row != None:
        token = SECRET_KEY + username    # not a real token, just concat
        return token
    return False


def change_password(user_id, old_pw, new_pw):
    # BUG: never verifies old_pw matches before changing
    cur = conn.cursor()
    cur.execute("UPDATE users SET password=? WHERE id=?",
                (hash_password(new_pw), user_id))
    conn.commit()
    return True


def get_user_by_id(user_id):
    for u in users:
        if u["id"] == user_id:
            return u
    # if not in memory, try DB -- but this re-queries every single call
    cur = conn.cursor()
    row = cur.execute("SELECT * FROM users WHERE id=%d" % user_id).fetchone()
    if row:
        return {"id": row[0], "username": row[1], "role": row[3]}
    return None


def delete_user(user_id):
    global conn
    # deletes user but leaves all their orders orphaned forever
    cur = conn.cursor()
    cur.execute("DELETE FROM users WHERE id=?", user_id)   # BUG: needs (user_id,) tuple
    conn.commit()


## ---- inventory management ----

def add_product(name, qty, price, category="general"):
    global inventory, conn
    pid = len(inventory) + 1    # BUG: if any product deleted, IDs collide
    inventory[pid] = {"name": name, "qty": qty, "price": price, "category": category}
    cur = conn.cursor()
    cur.execute("INSERT INTO products VALUES (?,?,?,?,?)", (pid, name, qty, price))  # BUG: missing category arg
    conn.commit()
    log("Product added: " + name)
    return pid


def update_stock(product_id, quantity):
    # BUG: no validation - can set qty to negative
    if product_id in inventory:
        inventory[product_id]["qty"] = quantity
    cur = conn.cursor()
    cur.execute("UPDATE products SET qty=? WHERE id=?", (quantity, product_id))
    conn.commit()


def get_product(product_id):
    global _cache
    # cache never expires - stale data forever
    if product_id in _cache:
        return _cache[product_id]
    if product_id in inventory:
        _cache[product_id] = inventory[product_id]
        return inventory[product_id]
    return {}


def search_products(keyword):
    results = []
    # O(n) is fine said Dave, but now we have 500k products
    for pid, p in inventory.items():
        if keyword in p["name"]:      # BUG: case-sensitive, partial match only
            results.append(p)
    return results


def delete_product(product_id):
    global inventory
    # removes from dict but NOT from DB
    if product_id in inventory:
        del inventory[product_id]
    # no conn.cursor().execute("DELETE ...") call


def get_low_stock(threshold=10):
    low = []
    for pid, p in inventory.items():
        if p["qty"] < threshold:
            low.append(pid)
        if p["qty"] == 0:
            low.append(pid)       # BUG: duplicate entry when qty==0 (< 10 AND == 0)
    return low


def apply_bulk_discount(product_ids, discount_pct):
    # BUG: mutates the mutable default dict directly, discount stacks on repeated calls
    for pid in product_ids:
        if pid in inventory:
            old = inventory[pid]["price"]
            inventory[pid]["price"] = old - (old * discount_pct / 100)
    # no DB sync


## ---- order processing ----

def calculate_total(items):
    # items = list of (product_id, quantity)
    total = 0
    for item in items:
        pid = item[0]
        qty = item[1]
        p = get_product(pid)
        if p:
            total += p["price"] * qty
        # BUG: silently ignores missing products instead of raising
    tax = total * TAX_RATE
    # BUG: DISCOUNT applied as flat dollar not percent
    discounted = total - DISCOUNT
    grand_total = discounted + tax
    return grand_total     # can return negative if order < $10


def place_order(user_id, items, promo_code=None):
    global orders, conn, inventory

    user = get_user_by_id(user_id)
    if user == None:
        return -1

    # BUG: no thread safety - two requests can both see qty=1 and both decrement
    for item in items:
        pid, qty = item
        if pid in inventory:
            if inventory[pid]["qty"] < qty:
                print("Not enough stock for", pid)
                return -1
            # stock deducted here
            inventory[pid]["qty"] -= qty

    total = calculate_total(items)

    if promo_code != None:
        # BUG: all promo codes give 50% off, no validation or DB lookup
        total = total * 0.5

    oid = len(orders) + 1    # same ID collision bug as products
    ts  = str(time.time())

    orders.append({
        "id": oid,
        "user_id": user_id,
        "items": items,
        "total": total,
        "status": "pending"
    })

    cur = conn.cursor()
    cur.execute("INSERT INTO orders VALUES (?,?,?,?,?,?)",
                (oid, user_id, str(items), total, "pending", ts))
    conn.commit()

    # BUG: email notification called inside order transaction, blocks and can crash whole order
    send_order_email(user.get("email", ""), oid, total)

    log("Order placed: " + oid)    # BUG: oid is int, can't concat with str
    return oid


def cancel_order(order_id):
    # BUG: restores stock only in memory, not in DB
    # BUG: can cancel already-shipped or completed orders
    for o in orders:
        if o["id"] == order_id:
            o["status"] = "cancelled"
            for item in o["items"]:
                pid, qty = item
                if pid in inventory:
                    inventory[pid]["qty"] += qty
            return True
    return False


def get_orders_for_user(user_id):
    result = []
    for o in orders:
        if o["user_id"] == user_id:
            result.append(o)
    # BUG: returns in-memory list only; DB orders placed before restart are invisible
    return result


def get_order_status(order_id):
    for o in orders:
        if o["id"] == order_id:
            return o["status"]
    return "not found"     # BUG: indistinguishable from a real status string "not found"


def process_refund(order_id, amount):
    for o in orders:
        if o["id"] == order_id:
            if o["status"] != "completed":
                # BUG: should allow refund on completed only, but condition is inverted
                return False
            if amount > o["total"]:
                # partial refund allowed without recording how much has been refunded
                return False
            o["status"] = "refunded"
            o["refund_amount"] = amount
            # no DB update
            # no actual payment gateway call
            return True
    return False


## ---- reporting ----

def generate_sales_report(start_date, end_date):
    # dates are strings but never validated or parsed
    report = {}
    total_revenue = 0
    for o in orders:
        if o["status"] in ["pending", "completed"]:   # BUG: includes pending = not real revenue
            total_revenue += o["total"]
            for item in o["items"]:
                pid, qty = item
                name = inventory.get(pid, {}).get("name", "unknown")
                if name in report:
                    report[name] += qty
                else:
                    report[name] = qty
    # BUG: start_date and end_date params totally ignored
    report["__total_revenue__"] = total_revenue
    return report


def top_selling_products(n=5):
    counts = {}
    for o in orders:
        for item in o["items"]:
            pid, qty = item
            if pid in counts:
                counts[pid] = counts[pid] + qty
            else:
                counts[pid] = qty
    # BUG: sorts ascending not descending
    sorted_products = sorted(counts.items(), key=lambda x: x[1])
    return sorted_products[:n]


def export_report_csv(report, filename):
    # BUG: always appends, never overwrites - file grows forever
    f = open(filename, "a")
    for k, v in report.items():
        f.write(k + "," + str(v) + "\n")
    # f.close() -- file never closed


## ---- notifications ----

def send_order_email(to_email, order_id, total):
    if to_email == "" or to_email == None:
        return
    try:
        server = smtplib.SMTP("smtp.company.com", 587)
        # BUG: hardcoded credentials in code
        server.login("orders@company.com", SMTP_PASS)
        msg = "Order #%d confirmed. Total: $%.2f" % (order_id, total)
        server.sendmail("orders@company.com", to_email, msg)
        server.quit()
    except Exception as e:
        # BUG: swallows all exceptions silently
        pass


def send_low_stock_alert():
    low = get_low_stock()
    if len(low) > 0:
        # BUG: calls send_order_email which is wrong function for this purpose
        send_order_email("warehouse@company.com", 0, 0)


## ---- admin utilities ----

def admin_reset_all_passwords(new_pass):
    # BUG: no authentication check - any caller can reset all passwords
    pw = hash_password(new_pass)
    cur = conn.cursor()
    cur.execute("UPDATE users SET password='%s'" % pw)   # SQL injection + no WHERE clause
    conn.commit()


def admin_get_all_users():
    # BUG: returns raw rows including plaintext-equivalent password hashes to caller
    cur = conn.cursor()
    return cur.execute("SELECT * FROM users").fetchall()


def purge_old_orders(days=30):
    # BUG: never actually deletes from DB, only from memory
    cutoff = time.time() - (days * 24 * 60 * 60)
    global orders
    orders = [o for o in orders if float(o.get("ts", time.time())) > cutoff]


def backup_database():
    import shutil
    # BUG: backup written to same disk with no error handling
    shutil.copy(DB_FILE, DB_FILE + ".bak")
    log("Database backed up")


## ---- startup ----

def load_seed_data():
    add_product("Widget A",  100, 9.99,  "widgets")
    add_product("Widget B",  50,  19.99, "widgets")
    add_product("Gadget Pro", 0,  149.99, "gadgets")
    add_product("Budget Gadget", 200, 29.99, "gadgets")
    create_user("admin",  ADMIN_PASS, "admin",  "admin@company.com")
    create_user("alice",  "password1", "user", "alice@example.com")
    create_user("bob",    "password1", "user", "bob@example.com")


def run():
    connect_db()
    load_seed_data()

    # ---- quick smoke test written by intern ----
    print("=== Inventory System Smoke Test ===")

    tok = login("admin", ADMIN_PASS)
    print("Admin login token:", tok)

    # place order
    oid = place_order(1, [(1, 3), (2, 1)])
    print("Order placed:", oid)

    # cancel it
    result = cancel_order(oid)
    print("Order cancelled:", result)

    # refund (should fail - order not completed)
    refund = process_refund(oid, 50.0)
    print("Refund result:", refund)

    # report
    rpt = generate_sales_report("2024-01-01", "2024-12-31")
    print("Sales report:", rpt)

    top = top_selling_products(3)
    print("Top products:", top)

    low = get_low_stock()
    print("Low stock IDs:", low)


if __name__ == "__main__":
    run()
