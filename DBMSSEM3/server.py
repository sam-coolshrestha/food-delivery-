from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import mysql.connector
import traceback

app = FastAPI()

# -----------------------------------------------------------
# CORS
# -----------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------------------------------------
# DB CONNECTION
# -----------------------------------------------------------
def get_conn():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="test123",
        database="food_delivery_db"
    )

# -----------------------------------------------------------
# RESTAURANTS
# -----------------------------------------------------------
@app.get("/restaurants")
def get_restaurants():
    conn = get_conn()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM restaurants;")
    data = cur.fetchall()
    cur.close()
    conn.close()
    return data


# -----------------------------------------------------------
# MENU ITEMS
# -----------------------------------------------------------
@app.get("/menu/{rid}")
def get_menu(rid: int):
    conn = get_conn()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM menu_items WHERE restaurant_id=%s", (rid,))
    data = cur.fetchall()
    cur.close()
    conn.close()
    return data


# -----------------------------------------------------------
# CUSTOMERS
# -----------------------------------------------------------
@app.post("/customers/add")
async def add_customer(request: Request):
    body = await request.json()
    print("Received customer body:", body)

    name = body.get("name")
    email = body.get("email")
    phone = body.get("phone")
    address = body.get("address")

    if not all([name, email]):
        raise HTTPException(status_code=400, detail="Missing fields")

    conn = get_conn()
    cur = conn.cursor(dictionary=True)

    # Check for existing email
    cur.execute("SELECT * FROM customers WHERE email=%s", (email,))
    existing = cur.fetchone()

    if existing:
        return {"status": "exists", "customer_id": existing["customer_id"]}

    # Insert new customer
    cur.execute("""
        INSERT INTO customers (name, email, phone, address)
        VALUES (%s, %s, %s, %s)
    """, (name, email, phone, address))

    conn.commit()
    customer_id = cur.lastrowid

    return {"status": "created", "customer_id": customer_id}


# -----------------------------------------------------------
# ADD ORDER
# -----------------------------------------------------------
@app.post("/orders/add")
async def add_order(request: Request):
    body = await request.json()
    print("Received order body:", body)

    customer_id = body.get("customer_id")
    restaurant_id = body.get("restaurant_id")
    items = body.get("items")

    if not all([customer_id, restaurant_id, items]):
        raise HTTPException(status_code=400, detail="Missing order fields")

    conn = get_conn()
    cur = conn.cursor()

    try:
        # Calculate total
        total = 0
        for it in items:
            cur.execute("SELECT price FROM menu_items WHERE item_id=%s", (it["item_id"],))
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=400, detail="Invalid item ID")

            total += float(row[0]) * it.get("quantity", 1)

        # Insert into orders table
        cur.execute(
            "INSERT INTO orders (customer_id, restaurant_id, total_amount, status) VALUES (%s, %s, %s, %s)",
            (customer_id, restaurant_id, total, "Pending")
        )
        order_id = cur.lastrowid

        # Insert order items
        for it in items:
            cur.execute(
                "INSERT INTO order_items (order_id, item_id, quantity, price_each) VALUES (%s, %s, %s, %s)",
                (order_id, it["item_id"], it["quantity"], total)
            )

        conn.commit()
        return {"status": "success", "order_id": order_id}

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        cur.close()
        conn.close()


# -----------------------------------------------------------
# GET ALL ORDERS (FIXED!)
# -----------------------------------------------------------
@app.get("/orders")
def get_orders():
    conn = get_conn()
    cur = conn.cursor(dictionary=True)

    # FULL ORDER DETAILS
    cur.execute("""
        SELECT 
            o.order_id,
            o.total_amount,
            o.status,
            o.created_at,
            c.name AS customer_name,
            r.name AS restaurant_name
        FROM orders o
        JOIN customers c ON o.customer_id = c.customer_id
        JOIN restaurants r ON o.restaurant_id = r.restaurant_id
        ORDER BY o.order_id DESC;
    """)

    orders = cur.fetchall()

    cur.close()
    conn.close()
    return orders
