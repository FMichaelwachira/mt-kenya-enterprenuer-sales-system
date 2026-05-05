import streamlit as st
import sqlite3
import hashlib
import pandas as pd
from datetime import datetime
import requests
from io import BytesIO
from PIL import Image
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

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

    # ── NEW: Settings table ───────────────────────────────────
    c.execute('''CREATE TABLE IF NOT EXISTS settings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        owner_phone TEXT,
        owner_email TEXT,
        at_username TEXT,
        at_api_key TEXT,
        gmail_address TEXT,
        gmail_app_password TEXT,
        sms_enabled INTEGER DEFAULT 0,
        email_enabled INTEGER DEFAULT 0
    )''')

    # Insert default empty settings row if not exists
    c.execute("SELECT COUNT(*) FROM settings")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO settings (owner_phone, owner_email, at_username, at_api_key, gmail_address, gmail_app_password, sms_enabled, email_enabled) VALUES ('', '', '', '', '', '', 0, 0)")

    owner_pass = hashlib.sha256('owner123'.encode()).hexdigest()
    c.execute("INSERT OR IGNORE INTO users (username, password, role) VALUES (?, ?, ?)",
              ('owner', owner_pass, 'owner'))

    conn.commit()
    conn.close()

# ── Get settings ──────────────────────────────────────────────
def get_settings():
    conn = sqlite3.connect('sales.db')
    c = conn.cursor()
    c.execute("SELECT * FROM settings LIMIT 1")
    row = c.fetchone()
    conn.close()
    if row:
        return {
            'id': row[0],
            'owner_phone': row[1],
            'owner_email': row[2],
            'at_username': row[3],
            'at_api_key': row[4],
            'gmail_address': row[5],
            'gmail_app_password': row[6],
            'sms_enabled': row[7],
            'email_enabled': row[8]
        }
    return None

# ── Send SMS via Africa's Talking ─────────────────────────────
def send_sms(message, settings):
    try:
        url = "https://api.africastalking.com/version1/messaging"
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
            "apiKey": settings['at_api_key']
        }
        data = {
            "username": settings['at_username'],
            "to": settings['owner_phone'],
            "message": message
        }
        response = requests.post(url, headers=headers, data=data)
        return response.status_code == 201
    except Exception as e:
        return False

# ── Send Email via Gmail SMTP ─────────────────────────────────
def send_email(subject, body, settings):
    try:
        msg = MIMEMultipart()
        msg['From'] = settings['gmail_address']
        msg['To'] = settings['owner_email']
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))

        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(settings['gmail_address'], settings['gmail_app_password'])
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        return False

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

            # ── Send SMS and Email notifications ─────────────
            settings = get_settings()
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            sms_message = (
                f"🏔️ NEW SALE ALERT!\n"
                f"Seller: {st.session_state.username}\n"
                f"Item: {item_name}\n"
                f"Qty: {int(quantity)}\n"
                f"Total: KSh {total:,.2f}\n"
                f"Time: {now}"
            )
            email_subject = f"🏔️ New Sale - KSh {total:,.2f} by {st.session_state.username}"
            email_body = (
                f"New Sale Recorded!\n\n"
                f"Seller: {st.session_state.username}\n"
                f"Item: {item_name}\n"
                f"Quantity: {int(quantity)}\n"
                f"Unit Price: KSh {unit_price:,.2f}\n"
                f"Total: KSh {total:,.2f}\n"
                f"Date & Time: {now}\n\n"
                f"-- Mt Kenya Entrepreneur's Ltd"
            )

            if settings and settings['sms_enabled'] and settings['at_api_key']:
                sms_sent = send_sms(sms_message, settings)
                if sms_sent:
                    st.info("📱 SMS alert sent to owner!")

            if settings and settings['email_enabled'] and settings['gmail_app_password']:
                email_sent = send_email(email_subject, email_body, settings)
                if email_sent:
                    st.info("📧 Email alert sent to owner!")

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

# ── Settings page ─────────────────────────────────────────────
def settings_page():
    st.markdown("<h3 style='color:#FFD700;'>⚙️ System Settings</h3>",
                unsafe_allow_html=True)

    settings = get_settings()

    st.markdown("""
        <div style='background:#1a2e1a; border: 1px solid #FFD700;
            border-radius: 10px; padding: 1rem; margin-bottom: 1rem;'>
            <p style='color:#90EE90; margin:0;'>
            Configure your SMS and Email notification settings below.
            These alerts will be sent to you every time a seller records a sale.
            </p>
        </div>
    """, unsafe_allow_html=True)

    st.markdown("<h4 style='color:#FFD700;'>📱 SMS Settings (Africa's Talking)</h4>",
                unsafe_allow_html=True)

    with st.expander("ℹ️ How to get Africa's Talking credentials", expanded=False):
        st.markdown("""
        1. Go to **https://africastalking.com** and create a free account
        2. Go to your **Dashboard → Settings → API Key**
        3. Copy your **Username** and **API Key**
        4. Add your phone number in international format e.g. **+254712345678**
        """)

    col1, col2 = st.columns(2)
    with col1:
        owner_phone = st.text_input("📱 Owner Phone Number",
                                     value=settings['owner_phone'] if settings else "",
                                     placeholder="+254712345678")
        at_username = st.text_input("👤 Africa's Talking Username",
                                     value=settings['at_username'] if settings else "",
                                     placeholder="your_username")
    with col2:
        at_api_key = st.text_input("🔑 Africa's Talking API Key",
                                    value=settings['at_api_key'] if settings else "",
                                    type="password",
                                    placeholder="Your API Key")
        sms_enabled = st.checkbox("✅ Enable SMS Notifications",
                                   value=bool(settings['sms_enabled']) if settings else False)

    st.markdown("<h4 style='color:#FFD700; margin-top:1rem;'>📧 Email Settings (Gmail)</h4>",
                unsafe_allow_html=True)

    with st.expander("ℹ️ How to get Gmail App Password", expanded=False):
        st.markdown("""
        1. Go to your **Google Account → Security**
        2. Enable **2-Step Verification** if not already on
        3. Search for **"App Passwords"**
        4. Create a new App Password for **Mail**
        5. Copy the **16-character password** generated
        6. Use your **Gmail address** and that **App Password** below
        """)

    col1, col2 = st.columns(2)
    with col1:
        owner_email = st.text_input("📧 Owner Email (where alerts go)",
                                     value=settings['owner_email'] if settings else "",
                                     placeholder="owner@gmail.com")
        gmail_address = st.text_input("📤 Gmail Address (sends the alerts)",
                                       value=settings['gmail_address'] if settings else "",
                                       placeholder="sender@gmail.com")
    with col2:
        gmail_app_password = st.text_input("🔑 Gmail App Password",
                                            value=settings['gmail_app_password'] if settings else "",
                                            type="password",
                                            placeholder="16-character app password")
        email_enabled = st.checkbox("✅ Enable Email Notifications",
                                     value=bool(settings['email_enabled']) if settings else False)

    st.markdown("<br>", unsafe_allow_html=True)

    if st.button("💾 Save Settings", use_container_width=True):
        conn = sqlite3.connect('sales.db')
        c = conn.cursor()
        c.execute("""UPDATE settings SET
            owner_phone=?, owner_email=?, at_username=?, at_api_key=?,
            gmail_address=?, gmail_app_password=?, sms_enabled=?, email_enabled=?
            WHERE id=1""",
            (owner_phone, owner_email, at_username, at_api_key,
             gmail_address, gmail_app_password,
             1 if sms_enabled else 0, 1 if email_enabled else 0))
        conn.commit()
        conn.close()
        st.success("✅ Settings saved successfully!")

    # ── Test buttons ──────────────────────────────────────────
    st.markdown("<h4 style='color:#FFD700; margin-top:1rem;'>🧪 Test Your Settings</h4>",
                unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        if st.button("📱 Send Test SMS", use_container_width=True):
            settings = get_settings()
            if not settings['at_api_key']:
                st.error("⚠️ Please save your Africa's Talking credentials first.")
            else:
                result = send_sms("🏔️ Test SMS from Mt Kenya Entrepreneur's Ltd! Your SMS alerts are working.", settings)
                if result:
                    st.success("✅ Test SMS sent successfully!")
                else:
                    st.error("❌ SMS failed. Check your credentials.")

    with col2:
        if st.button("📧 Send Test Email", use_container_width=True):
            settings = get_settings()
            if not settings['gmail_app_password']:
                st.error("⚠️ Please save your Gmail credentials first.")
            else:
                result = send_email(
                    "🏔️ Test Email - Mt Kenya Sales System",
                    "Your email alerts are working! You will receive notifications for every sale.",
                    settings)
                if result:
                    st.success("✅ Test Email sent successfully!")
                else:
                    st.error("❌ Email failed. Check your Gmail credentials.")

# ── Daily Summary ─────────────────────────────────────────────
def send_daily_summary(settings):
    conn = sqlite3.connect('sales.db')
    today = datetime.now().strftime("%Y-%m-%d")
    df = pd.read_sql_query(
        f"SELECT * FROM sales WHERE date_time LIKE '{today}%'", conn)
    conn.close()

    if df.empty:
        summary = f"📊 Daily Summary for {today}\n\nNo sales recorded today."
    else:
        total = df['total_price'].sum()
        count = len(df)
        top_seller = df.groupby('seller')['total_price'].sum().idxmax()
        summary = (
            f"📊 Daily Sales Summary — {today}\n\n"
            f"Total Revenue: KSh {total:,.2f}\n"
            f"Total Sales: {count}\n"
            f"Top Seller: {top_seller}\n\n"
            f"-- Mt Kenya Entrepreneur's Ltd"
        )

    if settings['sms_enabled'] and settings['at_api_key']:
        send_sms(summary[:160], settings)
    if settings['email_enabled'] and settings['gmail_app_password']:
        send_email(f"📊 Daily Summary {today}", summary, settings)

# ── Owner dashboard ───────────────────────────────────────────
def owner_page():
    show_header("Owner Dashboard")

    # Navigation tabs
    tab1, tab2, tab3, tab4 = st.tabs(["📊 Dashboard", "👥 Manage Sellers", "⚙️ Settings", "📊 Daily Summary"])

    with tab1:
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

    with tab2:
        st.markdown("<h3 style='color:#FFD700;'>👥 Manage Seller Accounts</h3>",
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

    with tab3:
        settings_page()

    with tab4:
        st.markdown("<h3 style='color:#FFD700;'>📊 Send Daily Summary</h3>",
                    unsafe_allow_html=True)
        st.markdown("""
            <div style='background:#1a2e1a; border: 1px solid #FFD700;
                border-radius: 10px; padding: 1rem; margin-bottom: 1rem;'>
                <p style='color:#90EE90; margin:0;'>
                Send today's sales summary via SMS and Email to the owner.
                </p>
            </div>
        """, unsafe_allow_html=True)

        if st.button("📤 Send Daily Summary Now", use_container_width=True):
            settings = get_settings()
            if not settings['at_api_key'] and not settings['gmail_app_password']:
                st.error("⚠️ Please configure your SMS or Email settings first.")
            else:
                send_daily_summary(settings)
                st.success("✅ Daily summary sent!")

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
