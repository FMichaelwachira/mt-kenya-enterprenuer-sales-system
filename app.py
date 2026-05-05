import streamlit as st
import sqlite3
import hashlib
import pandas as pd
from datetime import datetime
import requests
from io import BytesIO
from PIL import Image

# ── Mountain image from internet ─────────────────────────────
def load_mountain_image():
    url = "https://upload.wikimedia.org/wikipedia/commons/thumb/4/4e/Mount_Kenya.jpg/1280px-Mount_Kenya.jpg"
    try:
        response = requests.get(url)
        img = Image.open(BytesIO(response.content))
        return img
    except:
        return None

# ── Database setup ────────────────────────────────────────────
def init_db():
    conn = sqlite3.connect('sales.db')
    c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT NOT NULL
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS sales (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        seller TEXT NOT NULL,
        item_name TEXT NOT NULL,
        quantity INTEGER NOT NULL,
        unit_price REAL NOT NULL,
        total_price REAL NOT NULL,
        date_time TEXT NOT NULL
    )''')

    owner_pass = hashlib.sha256('owner123'.encode()).hexdigest()
    c.execute("INSERT OR IGNORE INTO users (username, password, role) VALUES (?, ?, ?)",
              ('owner', owner_pass, 'owner'))

    conn.commit()
    conn.close()

# ── Header ────────────────────────────────────────────────────
def show_header(subtitle=""):
    img = load_mountain_image()
    if img:
        st.image(img, use_column_width=True)
    st.markdown(f"""
        <div style='text-align: center; padding: 1rem 0;'>
            <h1 style='color: #FFD700; font-size: 2.5rem; font-weight: 800;
                text-shadow: 2px 2px 4px #000000;'>
                🏔️ Mt Kenya Entrepreneur's Ltd
            </h1>
            <p style='color: #90EE90; font-size: 1.1rem; font-style: italic;'>
                {subtitle}
            </p>
            <hr style='border: 2px solid #FFD700; margin: 0.5rem 0;'>
        </div>
    """, unsafe_allow_html=True)

# ── Login page ────────────────────────────────────────────────
def login():
    show_header("Sales Management System")

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("""
            <div style='background:#243d24; border: 2px solid #FFD700;
                border-radius: 12px; padding: 2rem; margin-top: 1rem;'>
                <h3 style='color: #FFD700; text-align: center;
                    margin-bottom: 1rem;'>🔐 Login to Your Account</h3>
            </div>
        """, unsafe_allow_html=True)

        username = st.text_input("👤 Username")
        password = st.text_input("🔑 Password", type="password")

        if st.button("Login", use_container_width=True):
            conn = sqlite3.connect('sales.db')
            c = conn.cursor()
            hashed = hashlib.sha256(password.encode()).hexdigest()
            c.execute("SELECT * FROM users WHERE username=? AND password=?",
                      (username, hashed))
            user = c.fetchone()
            conn.close()

            if user:
                st.session_state.logged_in = True
                st.session_state.username = user[1]
                st.session_state.role = user[3]
                st.rerun()
            else:
                st.error("❌ Wrong username or password. Try again.")

        st.markdown("""
            <p style='color: #90EE90; text-align: center;
                font-size: 0.85rem; margin-top: 1rem;'>
                🏔️ Powered by Mt Kenya Entrepreneur's Ltd
            </p>
        """, unsafe_allow_html=True)

# ── Seller page ───────────────────────────────────────────────
def seller_page():
    show_header(f"Seller Portal — Welcome, {st.session_state.username}!")

    st.markdown("<h3 style='color:#FFD700;'>📝 Record a New Sale</h3>",
                unsafe_allow_html=True)

    with st.container():
        st.markdown("""
            <div style='background:#243d24; border: 1px solid #FFD700;
                border-radius: 10px; padding: 1rem;'>
        """, unsafe_allow_html=True)

        col1, col2 = st.columns(2)
        with col1:
            item_name = st.text_input("🛒 Item Name")
            quantity = st.number_input("📦 Quantity", min_value=1, step=1)
        with col2:
            unit_price = st.number_input("💵 Unit Price (KSh)",
                                          min_value=0.0, step=10.0)
            total = quantity * unit_price
            st.markdown(f"""
                <div style='background:#1a2e1a; border: 2px solid #FFD700;
                    border-radius: 10px; padding: 1rem; margin-top: 1.5rem;
                    text-align: center;'>
                    <p style='color:#90EE90; margin:0;
                        font-size:0.85rem;'>Auto-calculated Total</p>
                    <h2 style='color:#FFD700; margin:0;
                        font-size:2rem;'>KSh {total:,.2f}</h2>
                </div>
            """, unsafe_allow_html=True)

        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    if st.button("✅ Record Sale", use_container_width=True):
        if item_name.strip() == "":
            st.error("⚠️ Please enter an item name.")
        elif total == 0:
            st.error("⚠️ Please enter quantity and price.")
        else:
            conn = sqlite3.connect('sales.db')
            c = conn.cursor()
            c.execute("""INSERT INTO sales
                (seller, item_name, quantity, unit_price, total_price, date_time)
                VALUES (?, ?, ?, ?, ?, ?)""",
                (st.session_state.username, item_name, int(quantity),
                 unit_price, total,
                 datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            conn.commit()
            conn.close()
            st.success(f"✅ Sale recorded successfully! Total: KSh {total:,.2f}")
            st.balloons()

    st.markdown("<h3 style='color:#FFD700; margin-top:2rem;'>📊 Your Sales History</h3>",
                unsafe_allow_html=True)

    conn = sqlite3.connect('sales.db')
    c = conn.cursor()
    c.execute("""SELECT item_name, quantity, unit_price, total_price, date_time
                 FROM sales WHERE seller=? ORDER BY date_time DESC""",
              (st.session_state.username,))
    rows = c.fetchall()
    conn.close()

    if rows:
        df = pd.DataFrame(rows,
            columns=["Item", "Qty", "Unit Price (KSh)", "Total (KSh)", "Date & Time"])
        st.dataframe(df, use_container_width=True)

        total_earned = df["Total (KSh)"].sum()
        st.markdown(f"""
            <div style='background:#243d24; border: 2px solid #FFD700;
                border-radius: 10px; padding: 1rem; text-align: center;
                margin-top: 1rem;'>
                <p style='color:#90EE90; margin:0;'>Your Total Sales</p>
                <h2 style='color:#FFD700; margin:0;'>KSh {total_earned:,.2f}</h2>
            </div>
        """, unsafe_allow_html=True)
    else:
        st.info("📭 No sales recorded yet. Start recording your first sale above!")

    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("🚪 Logout", use_container_width=True):
        st.session_state.clear()
        st.rerun()

# ── Owner dashboard ───────────────────────────────────────────
def owner_page():
    show_header("Owner Dashboard")

    conn = sqlite3.connect('sales.db')
    df = pd.read_sql_query(
        "SELECT * FROM sales ORDER BY date_time DESC", conn)
    conn.close()

    if df.empty:
        st.info("📭 No sales recorded yet.")
    else:
        total_revenue = df['total_price'].sum()
        total_sales = len(df)
        total_items = df['quantity'].sum()
        top_seller = df.groupby('seller')['total_price'].sum().idxmax()

        st.markdown("<h3 style='color:#FFD700;'>📊 Business Summary</h3>",
                    unsafe_allow_html=True)

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("💰 Total Revenue", f"KSh {total_revenue:,.2f}")
        col2.metric("🧾 Total Sales", total_sales)
        col3.metric("📦 Items Sold", int(total_items))
        col4.metric("🏆 Top Seller", top_seller)

        st.markdown("<h3 style='color:#FFD700; margin-top:1.5rem;'>💹 Revenue by Seller</h3>",
                    unsafe_allow_html=True)
        seller_totals = df.groupby('seller')['total_price'].sum()
        st.bar_chart(seller_totals)

        st.markdown("<h3 style='color:#FFD700;'>📈 Sales Over Time</h3>",
                    unsafe_allow_html=True)
        df['date'] = pd.to_datetime(df['date_time']).dt.date
        daily_sales = df.groupby('date')['total_price'].sum()
        st.line_chart(daily_sales)

        st.markdown("<h3 style='color:#FFD700;'>🏷️ Top Selling Items</h3>",
                    unsafe_allow_html=True)
        top_items = df.groupby('item_name')['quantity'].sum().sort_values(
            ascending=False).head(10)
        st.bar_chart(top_items)

        st.markdown("<h3 style='color:#FFD700;'>📋 All Sales Records</h3>",
                    unsafe_allow_html=True)

        col1, col2 = st.columns(2)
        with col1:
            sellers = ['All'] + list(df['seller'].unique())
            selected_seller = st.selectbox("Filter by Seller", sellers)
        with col2:
            dates = ['All'] + list(df['date'].astype(str).unique())
            selected_date = st.selectbox("Filter by Date", dates)

        filtered_df = df.copy()
        if selected_seller != 'All':
            filtered_df = filtered_df[filtered_df['seller'] == selected_seller]
        if selected_date != 'All':
            filtered_df = filtered_df[
                filtered_df['date'].astype(str) == selected_date]

        st.dataframe(
            filtered_df[['seller', 'item_name', 'quantity',
                         'unit_price', 'total_price', 'date_time']],
            use_container_width=True)

        csv = filtered_df.to_csv(index=False)
        st.download_button("📥 Export to CSV", csv,
                           "mt_kenya_sales.csv", "text/csv",
                           use_container_width=True)

    st.markdown("<h3 style='color:#FFD700; margin-top:1.5rem;'>👥 Manage Seller Accounts</h3>",
                unsafe_allow_html=True)

    with st.expander("➕ Add New Seller Account"):
        new_username = st.text_input("New Seller Username")
        new_password = st.text_input("New Seller Password", type="password")
        if st.button("Add Seller", use_container_width=True):
            if new_username.strip() == "" or new_password.strip() == "":
                st.error("⚠️ Please fill in both fields.")
            else:
                try:
                    conn = sqlite3.connect('sales.db')
                    c = conn.cursor()
                    hashed = hashlib.sha256(new_password.encode()).hexdigest()
                    c.execute(
                        "INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
                        (new_username, hashed, 'seller'))
                    conn.commit()
                    conn.close()
                    st.success(f"✅ Seller '{new_username}' added successfully!")
                except:
                    st.error("⚠️ Username already exists. Try a different one.")

    with st.expander("👀 View All Seller Accounts"):
        conn = sqlite3.connect('sales.db')
        users_df = pd.read_sql_query(
            "SELECT username, role FROM users", conn)
        conn.close()
        st.dataframe(users_df, use_container_width=True)

    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("🚪 Logout", use_container_width=True):
        st.session_state.clear()
        st.rerun()

# ── Main ──────────────────────────────────────────────────────
init_db()

if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    login()
else:
    if st.session_state.role == 'seller':
        seller_page()
    else:
        owner_page()