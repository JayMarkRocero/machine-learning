"""
Rosario Dairy — Realistic Dummy Data Generator
Generates 2 years of dairy sales data with:
  - Seasonal trends
  - Weekend spikes
  - Holiday demand increases
  - FEFO inventory batches (FIXED: proper expiry status)
  - 10,000+ transactions
"""

import random
import numpy as np
import pandas as pd
from datetime import date, timedelta, datetime
from sqlalchemy import create_engine, text
import warnings
warnings.filterwarnings("ignore")

# ── Configuration ──────────────────────────────────────────
DB_CONFIG = {
    "host":     "localhost",
    "port":     3306,
    "user":     "root",
    "password": "",          # your MySQL password (blank if none)
    "database": "rosario_dairy"
}

random.seed(42)
np.random.seed(42)

TODAY      = date(2026, 5, 13)   # today's actual date
START_DATE = date(2024, 6, 1)    # sales history start
END_DATE   = date(2026, 5, 12)   # sales history end (yesterday)

# ── Products ────────────────────────────────────────────────
PRODUCTS = [
    {"code": "MLK-001", "name": "Fresh Milk 1L",            "category": "milk",      "unit": "1L",   "price": 85.00,  "cost": 60.00,  "reorder": 100, "shelf_days": 7},
    {"code": "MLK-002", "name": "Fresh Milk 500mL",         "category": "milk",      "unit": "500mL","price": 45.00,  "cost": 30.00,  "reorder": 80,  "shelf_days": 7},
    {"code": "MLK-003", "name": "Full Cream Milk 1L",       "category": "milk",      "unit": "1L",   "price": 95.00,  "cost": 68.00,  "reorder": 60,  "shelf_days": 10},
    {"code": "YOG-001", "name": "Plain Yogurt 200g",        "category": "yogurt",    "unit": "200g", "price": 55.00,  "cost": 35.00,  "reorder": 70,  "shelf_days": 21},
    {"code": "YOG-002", "name": "Strawberry Yogurt 200g",   "category": "yogurt",    "unit": "200g", "price": 60.00,  "cost": 38.00,  "reorder": 70,  "shelf_days": 21},
    {"code": "YOG-003", "name": "Yogurt Drink 250mL",       "category": "yogurt",    "unit": "250mL","price": 35.00,  "cost": 20.00,  "reorder": 90,  "shelf_days": 14},
    {"code": "CHE-001", "name": "Cheddar Cheese 250g",      "category": "cheese",    "unit": "250g", "price": 150.00, "cost": 100.00, "reorder": 40,  "shelf_days": 60},
    {"code": "CHE-002", "name": "Cheese Spread 200g",       "category": "cheese",    "unit": "200g", "price": 120.00, "cost": 80.00,  "reorder": 40,  "shelf_days": 45},
    {"code": "BUT-001", "name": "Salted Butter 200g",       "category": "butter",    "unit": "200g", "price": 130.00, "cost": 90.00,  "reorder": 50,  "shelf_days": 90},
    {"code": "BUT-002", "name": "Unsalted Butter 200g",     "category": "butter",    "unit": "200g", "price": 130.00, "cost": 90.00,  "reorder": 30,  "shelf_days": 90},
    {"code": "ICE-001", "name": "Vanilla Ice Cream 1L",     "category": "ice_cream", "unit": "1L",   "price": 180.00, "cost": 120.00, "reorder": 40,  "shelf_days": 180},
    {"code": "ICE-002", "name": "Chocolate Ice Cream 1L",   "category": "ice_cream", "unit": "1L",   "price": 180.00, "cost": 120.00, "reorder": 40,  "shelf_days": 180},
]

# Philippine public holidays
HOLIDAYS = {
    date(2024, 1, 1), date(2024, 3, 28), date(2024, 3, 29),
    date(2024, 4, 9), date(2024, 5, 1),  date(2024, 6, 12),
    date(2024, 8, 26), date(2024, 11, 1), date(2024, 11, 2),
    date(2024, 12, 8), date(2024, 12, 25), date(2024, 12, 30),
    date(2025, 1, 1), date(2025, 4, 17), date(2025, 4, 18),
    date(2025, 4, 9), date(2025, 5, 1),  date(2025, 6, 12),
    date(2025, 8, 25), date(2025, 11, 1), date(2025, 11, 2),
    date(2025, 12, 8), date(2025, 12, 25), date(2025, 12, 30),
    date(2026, 1, 1),
}

# Base daily demand per product
BASE_DEMAND = {
    "MLK-001": 35, "MLK-002": 28, "MLK-003": 20,
    "YOG-001": 22, "YOG-002": 25, "YOG-003": 30,
    "CHE-001": 12, "CHE-002": 10,
    "BUT-001": 15, "BUT-002":  8,
    "ICE-001": 18, "ICE-002": 16,
}


def get_demand_multiplier(sale_date: date, category: str) -> float:
    multiplier = 1.0
    if sale_date.weekday() == 5:   multiplier *= 1.40
    elif sale_date.weekday() == 6: multiplier *= 1.25
    if category == "ice_cream" and sale_date.month in [3, 4, 5]:
        multiplier *= 1.60
    if category == "ice_cream" and sale_date.month in [7, 8, 9]:
        multiplier *= 0.75
    if sale_date.month == 12:
        multiplier *= 1.35
    if category in ["cheese", "butter"] and sale_date.month == 12:
        multiplier *= 1.50
    if sale_date.month == 1 and sale_date.day <= 7:
        multiplier *= 1.20
    if sale_date in HOLIDAYS:
        multiplier *= 1.30
        if category == "milk":
            multiplier *= 0.70
    if category == "milk" and sale_date.month in [6, 7, 8]:
        multiplier *= 0.90
    return multiplier


def generate_daily_quantities(sale_date: date, product_code: str, category: str) -> int:
    base  = BASE_DEMAND.get(product_code, 15)
    mult  = get_demand_multiplier(sale_date, category)
    noise = np.random.normal(0, 0.12)
    qty   = int(base * mult * (1 + noise))
    return max(1, qty)


def build_transaction_code(sale_date: date, seq: int) -> str:
    return f"TXN-{sale_date.strftime('%Y%m%d')}-{seq:04d}"


def build_batch_code(product_id: int, received: date, seq: int) -> str:
    return f"BAT-{product_id:03d}-{received.strftime('%Y%m%d')}-{seq:03d}"


def get_batch_status_and_qty(expiry: date, initial_qty: int, reorder: int) -> tuple:
    """
    Determine realistic batch_status and current_quantity based on expiry vs today.
    Returns (status, current_quantity)
    """
    days_until_expiry = (expiry - TODAY).days

    if days_until_expiry < 0:
        # Already expired
        return 'expired', 0

    elif days_until_expiry <= 3:
        # Expiring very soon — critically low stock
        return 'active', random.randint(2, 15)

    elif days_until_expiry <= 7:
        # Expiring soon — low stock
        return 'active', random.randint(10, 30)

    elif days_until_expiry <= 14:
        # Expiring within 2 weeks — moderate stock
        return 'active', random.randint(20, 60)

    else:
        # Fresh batch — good stock level
        curr = random.randint(reorder * 2, reorder * 4)
        return 'active', curr


# ── Main Generator ──────────────────────────────────────────
def main():
    engine = create_engine(
        f"mysql+pymysql://{DB_CONFIG['user']}:{DB_CONFIG['password']}"
        f"@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}",
        echo=False
    )

    print("🥛 Rosario Dairy — Dummy Data Generator")
    print("=" * 50)
    print(f"   Today:      {TODAY}")
    print(f"   Sales from: {START_DATE} → {END_DATE}")
    print()

    with engine.begin() as conn:
        # Clear existing data
        conn.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
        for tbl in ["reorder_recommendations", "forecast_results",
                    "sales_items", "sales_transactions",
                    "inventory", "products"]:
            conn.execute(text(f"TRUNCATE TABLE {tbl}"))
        conn.execute(text("SET FOREIGN_KEY_CHECKS = 1"))
        print("✓ Tables cleared")

        # ── 1. Insert Products ─────────────────────────────
        for p in PRODUCTS:
            conn.execute(text("""
                INSERT INTO products
                  (product_code, product_name, category, unit,
                   unit_price, cost_price, reorder_level, shelf_life_days)
                VALUES
                  (:code, :name, :cat, :unit,
                   :price, :cost, :reorder, :shelf)
            """), {
                "code":   p["code"],   "name":   p["name"],
                "cat":    p["category"], "unit":  p["unit"],
                "price":  p["price"],  "cost":   p["cost"],
                "reorder": p["reorder"], "shelf": p["shelf_days"]
            })
        print(f"✓ Inserted {len(PRODUCTS)} products")

        # Fetch product IDs
        result = conn.execute(text(
            "SELECT product_id, product_code, shelf_life_days FROM products"
        ))
        product_map = {row.product_code: (row.product_id, row.shelf_life_days)
                       for row in result}

        # ── 2. Generate Inventory Batches ──────────────────
        # Only generate batches for the last (shelf_days * 3) window up to today + 30
        # This ensures we have a realistic mix of active and expired batches
        batch_seq    = 1
        active_count = 0
        expired_count = 0

        for p in PRODUCTS:
            pid, shelf = product_map[p["code"]]

            # Restock interval: weekly for milk, biweekly for yogurt/cheese, monthly for butter/ice cream
            if shelf <= 10:
                restock_interval = 7
            elif shelf <= 21:
                restock_interval = 10
            elif shelf <= 60:
                restock_interval = 14
            else:
                restock_interval = 30

            # Generate batches starting from enough history to have some expired ones
            # but not too far back to avoid all-expired scenario
            history_start = TODAY - timedelta(days=shelf * 3)
            current = history_start

            while current <= TODAY + timedelta(days=30):
                initial_qty = random.randint(
                    p["reorder"] * 3,
                    p["reorder"] * 6
                )
                received   = current
                production = received - timedelta(days=random.randint(1, 3))
                expiry     = production + timedelta(days=shelf)

                # ✅ KEY FIX: Determine status based on expiry vs TODAY
                status, curr_qty = get_batch_status_and_qty(
                    expiry, initial_qty, p["reorder"]
                )

                if status == 'active':
                    active_count += 1
                else:
                    expired_count += 1

                conn.execute(text("""
                    INSERT INTO inventory
                      (product_id, batch_code, production_date, expiry_date,
                       received_date, initial_quantity, current_quantity,
                       unit_cost, batch_status)
                    VALUES
                      (:pid, :bcode, :prod_d, :exp_d,
                       :recv_d, :init_q, :curr_q,
                       :ucost, :status)
                """), {
                    "pid":    pid,
                    "bcode":  build_batch_code(pid, received, batch_seq),
                    "prod_d": production,
                    "exp_d":  expiry,
                    "recv_d": received,
                    "init_q": initial_qty,
                    "curr_q": curr_qty,
                    "ucost":  p["cost"],
                    "status": status
                })
                batch_seq += 1
                current += timedelta(days=restock_interval)

        print(f"✓ Inserted {batch_seq - 1} inventory batches")
        print(f"  — Active:  {active_count}")
        print(f"  — Expired: {expired_count}")

        # ── 3. Generate Sales Transactions ────────────────
        txn_seq   = 1
        item_rows = []
        txn_rows  = []

        current_date = START_DATE
        while current_date <= END_DATE:
            daily_txn_count = random.randint(8, 30)
            if current_date.weekday() in [5, 6]:
                daily_txn_count = random.randint(20, 45)
            if current_date in HOLIDAYS:
                daily_txn_count = random.randint(25, 50)

            for _ in range(daily_txn_count):
                hour     = random.randint(7, 19)
                minute   = random.randint(0, 59)
                second   = random.randint(0, 59)
                txn_time = f"{hour:02d}:{minute:02d}:{second:02d}"

                txn_code   = build_transaction_code(current_date, txn_seq)
                cashier_id = random.randint(1, 4)
                payment    = random.choices(
                    ["cash", "gcash", "card"],
                    weights=[60, 25, 15]
                )[0]

                n_items          = random.randint(2, 6)
                selected_products = random.sample(PRODUCTS, min(n_items, len(PRODUCTS)))

                subtotal    = 0.0
                items_batch = []

                for sp in selected_products:
                    pid, _ = product_map[sp["code"]]
                    qty    = generate_daily_quantities(current_date, sp["code"], sp["category"])
                    qty    = max(1, min(qty, 20))
                    disc   = random.choice([0, 0, 0, 5, 10])
                    price  = sp["price"]
                    line   = round(qty * price * (1 - disc / 100), 2)
                    subtotal += line

                    items_batch.append({
                        "txn_code": txn_code,
                        "pid":  pid,
                        "qty":  qty,
                        "price": price,
                        "disc": disc,
                        "line": line
                    })

                total = round(subtotal, 2)

                txn_rows.append({
                    "code":    txn_code,
                    "date":    current_date,
                    "time":    txn_time,
                    "cashier": cashier_id,
                    "sub":     subtotal,
                    "disc":    0.00,
                    "tax":     0.00,
                    "total":   total,
                    "pay":     payment
                })

                for it in items_batch:
                    item_rows.append(it)

                txn_seq += 1

            current_date += timedelta(days=1)

        # Bulk insert transactions
        BATCH_SIZE = 500

        for i in range(0, len(txn_rows), BATCH_SIZE):
            batch = txn_rows[i:i + BATCH_SIZE]
            conn.execute(text("""
                INSERT INTO sales_transactions
                  (transaction_code, transaction_date, transaction_time,
                   cashier_id, subtotal, discount_amount, tax_amount,
                   total_amount, payment_method)
                VALUES
                  (:code, :date, :time, :cashier,
                   :sub, :disc, :tax, :total, :pay)
            """), batch)

        print(f"✓ Inserted {len(txn_rows):,} sales transactions")

        # Fetch transaction IDs
        result = conn.execute(text(
            "SELECT transaction_id, transaction_code FROM sales_transactions"
        ))
        txn_id_map = {row.transaction_code: row.transaction_id for row in result}

        # Bulk insert items
        item_insert_rows = []
        for it in item_rows:
            tid = txn_id_map.get(it["txn_code"])
            if tid:
                item_insert_rows.append({
                    "tid":   tid,
                    "pid":   it["pid"],
                    "qty":   it["qty"],
                    "price": it["price"],
                    "disc":  it["disc"],
                    "line":  it["line"]
                })

        for i in range(0, len(item_insert_rows), BATCH_SIZE):
            batch = item_insert_rows[i:i + BATCH_SIZE]
            conn.execute(text("""
                INSERT INTO sales_items
                  (transaction_id, product_id, quantity, unit_price,
                   discount_pct, line_total)
                VALUES (:tid, :pid, :qty, :price, :disc, :line)
            """), batch)

        print(f"✓ Inserted {len(item_insert_rows):,} sales line items")

        # ── 4. Summary ────────────────────────────────────
        print(f"\n✅ Done!")
        print(f"   Date range:        {START_DATE} → {END_DATE}")
        print(f"   Products:          {len(PRODUCTS)}")
        print(f"   Inventory batches: {batch_seq - 1} ({active_count} active, {expired_count} expired)")
        print(f"   Transactions:      {len(txn_rows):,}")
        print(f"   Line items:        {len(item_insert_rows):,}")
        print()
        print("📦 Active inventory summary:")

    # Verify active stock outside transaction
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT p.product_name,
                   COUNT(i.batch_id)          AS active_batches,
                   SUM(i.current_quantity)    AS total_stock,
                   MIN(i.expiry_date)         AS nearest_expiry
            FROM inventory i
            JOIN products p ON i.product_id = p.product_id
            WHERE i.batch_status = 'active'
              AND i.expiry_date >= :today
            GROUP BY p.product_id, p.product_name
            ORDER BY p.product_name
        """), {"today": TODAY})

        rows = result.fetchall()
        if rows:
            print(f"   {'Product':<30} {'Batches':>8} {'Stock':>8} {'Nearest Expiry':>15}")
            print("   " + "-" * 65)
            for row in rows:
                print(f"   {row.product_name:<30} {row.active_batches:>8} "
                      f"{row.total_stock:>8} {str(row.nearest_expiry):>15}")
        else:
            print("   ⚠ No active inventory found!")


if __name__ == "__main__":
    main()