from flask import Flask, render_template, request, redirect, url_for, session, jsonify, Response
import sqlite3
import hashlib
from datetime import datetime, date
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import requests
import io
import csv

app = Flask(__name__)
app.secret_key = 'enterprise_secret_key_2026'

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
        amount_paid REAL NOT NULL DEFAULT 0,
        change_given REAL NOT NULL DEFAULT 0,
        payment_method TEXT DEFAULT 'Cash',
        date_time TEXT NOT NULL
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS settings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        business_name TEXT DEFAULT 'My Business',
        business_location TEXT DEFAULT '',
        business_currency TEXT DEFAULT 'KSh',
        business_color TEXT DEFAULT '#1565C0',
        owner_phone TEXT DEFAULT '',
        owner_email TEXT DEFAULT '',
        at_username TEXT DEFAULT '',
        at_api_key TEXT DEFAULT '',
        gmail_address TEXT DEFAULT '',
        gmail_app_password TEXT DEFAULT '',
        sms_enabled INTEGER DEFAULT 0,
        email_enabled INTEGER DEFAULT 0,
        low_stock_threshold INTEGER DEFAULT 5
    )''')

    # ── NEW: Inventory table ──────────────────────────────────
    c.execute('''CREATE TABLE IF NOT EXISTS inventory (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_name TEXT UNIQUE NOT NULL,
        category TEXT DEFAULT 'General',
        buying_price REAL NOT NULL DEFAULT 0,
        selling_price REAL NOT NULL DEFAULT 0,
        stock_quantity INTEGER NOT NULL DEFAULT 0,
        low_stock_level INTEGER NOT NULL DEFAULT 5,
        expiry_date TEXT DEFAULT NULL,
        date_added TEXT NOT NULL
    )''')

    # ── NEW: Payment methods table ───────────────────────────
    c.execute('''CREATE TABLE IF NOT EXISTS payment_methods (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        method_name TEXT NOT NULL,
        method_type TEXT NOT NULL,
        details TEXT NOT NULL,
        is_active INTEGER DEFAULT 1
    )''')

    # ── NEW: Expenses table ──────────────────────────────────
    c.execute('''CREATE TABLE IF NOT EXISTS expenses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        description TEXT NOT NULL,
        amount REAL NOT NULL,
        category TEXT DEFAULT 'General',
        date_time TEXT NOT NULL
    )''')

    # ── NEW: Activity log table ───────────────────────────────
    c.execute('''CREATE TABLE IF NOT EXISTS activity_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL,
        action TEXT NOT NULL,
        details TEXT NOT NULL,
        date_time TEXT NOT NULL
    )''')

    c.execute("SELECT COUNT(*) FROM settings")
    if c.fetchone()[0] == 0:
        c.execute("""INSERT INTO settings
            (business_name,business_location,business_currency,business_color,
             owner_phone,owner_email,at_username,at_api_key,
             gmail_address,gmail_app_password,sms_enabled,email_enabled,low_stock_threshold)
            VALUES ('My Business','','KSh','#1565C0','','','','','','',0,0,5)""")

    for col in [
        "ALTER TABLE sales ADD COLUMN amount_paid REAL NOT NULL DEFAULT 0",
        "ALTER TABLE sales ADD COLUMN payment_method TEXT DEFAULT 'Cash'",
        "ALTER TABLE sales ADD COLUMN change_given REAL NOT NULL DEFAULT 0",
        "ALTER TABLE settings ADD COLUMN business_name TEXT DEFAULT 'My Business'",
        "ALTER TABLE settings ADD COLUMN business_location TEXT DEFAULT ''",
        "ALTER TABLE settings ADD COLUMN business_currency TEXT DEFAULT 'KSh'",
        "ALTER TABLE settings ADD COLUMN business_color TEXT DEFAULT '#1565C0'",
        "ALTER TABLE settings ADD COLUMN low_stock_threshold INTEGER DEFAULT 5"
    ]:
        try: c.execute(col)
        except: pass

    owner_pass = hashlib.sha256('owner123'.encode()).hexdigest()
    c.execute("INSERT OR IGNORE INTO users (username,password,role) VALUES (?,?,?)",
              ('owner', owner_pass, 'owner'))
    conn.commit()
    conn.close()

def get_db():
    conn = sqlite3.connect('sales.db')
    conn.row_factory = sqlite3.Row
    return conn

def get_settings():
    conn = get_db()
    row = conn.execute("SELECT * FROM settings LIMIT 1").fetchone()
    conn.close()
    return dict(row) if row else {}

def log_activity(username, action, details):
    conn = get_db()
    conn.execute("INSERT INTO activity_log (username,action,details,date_time) VALUES (?,?,?,?)",
                 (username, action, details, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()

def get_low_stock_products():
    conn = get_db()
    products = conn.execute("""SELECT * FROM inventory
        WHERE stock_quantity <= low_stock_level
        ORDER BY stock_quantity ASC""").fetchall()
    conn.close()
    return [dict(p) for p in products]

def get_expiring_soon():
    conn = get_db()
    today = date.today().isoformat()
    products = conn.execute("""SELECT * FROM inventory
        WHERE expiry_date IS NOT NULL
        AND expiry_date != ''
        AND expiry_date <= date('now', '+7 days')
        AND expiry_date >= ?
        ORDER BY expiry_date ASC""", (today,)).fetchall()
    conn.close()
    return [dict(p) for p in products]

def send_sms(message, settings):
    try:
        url = "https://api.africastalking.com/version1/messaging"
        headers = {"Accept":"application/json","Content-Type":"application/x-www-form-urlencoded","apiKey":settings['at_api_key']}
        data = {"username":settings['at_username'],"to":settings['owner_phone'],"message":message}
        r = requests.post(url, headers=headers, data=data)
        return r.status_code == 201
    except: return False

def send_email(subject, body, settings):
    try:
        msg = MIMEMultipart()
        msg['From'] = settings['gmail_address']
        msg['To'] = settings['owner_email']
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))
        s = smtplib.SMTP('smtp.gmail.com', 587)
        s.ehlo(); s.starttls(); s.ehlo()
        s.login(settings['gmail_address'], settings['gmail_app_password'])
        s.send_message(msg); s.quit()
        return True, None
    except Exception as e: return False, str(e)

# ── LOGIN ─────────────────────────────────────────────────────
@app.route('/', methods=['GET','POST'])
def login():
    error = None
    settings = get_settings()
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        hashed = hashlib.sha256(password.encode()).hexdigest()
        conn = get_db()
        user = conn.execute("SELECT * FROM users WHERE username=? AND password=?",(username,hashed)).fetchone()
        conn.close()
        if user:
            session['logged_in'] = True
            session['username'] = user['username']
            session['role'] = user['role']
            log_activity(user['username'], 'LOGIN', f"{user['username']} logged in")
            return redirect(url_for('owner' if user['role']=='owner' else 'seller'))
        else:
            error = "Wrong username or password. Try again."
    return render_template('login.html', error=error, settings=settings)

@app.route('/logout')
def logout():
    if session.get('username'):
        log_activity(session['username'], 'LOGOUT', f"{session['username']} logged out")
    session.clear()
    return redirect(url_for('login'))

# ── SELLER ────────────────────────────────────────────────────
@app.route('/seller', methods=['GET','POST'])
def seller():
    if not session.get('logged_in') or session.get('role') != 'seller':
        return redirect(url_for('login'))
    settings = get_settings()
    success = error = last_sale = None

    if request.method == 'POST':
        item_name = request.form['item_name'].strip()
        quantity = int(request.form['quantity'])
        unit_price = float(request.form['unit_price'])
        amount_paid = float(request.form.get('amount_paid', 0))
        total = quantity * unit_price
        change = amount_paid - total

        if not item_name:
            error = "Please enter an item name."
        elif total == 0:
            error = "Please enter quantity and price."
        elif amount_paid < total:
            error = f"Amount paid ({settings['business_currency']} {amount_paid:,.2f}) is less than total ({settings['business_currency']} {total:,.2f})."
        else:
            # ── Check stock availability ──────────────────────
            conn = get_db()
            product = conn.execute("SELECT * FROM inventory WHERE product_name=?", (item_name,)).fetchone()

            if product and product['stock_quantity'] < quantity:
                error = f"Insufficient stock! Only {product['stock_quantity']} units of {item_name} available."
                conn.close()
            else:
                payment_method = request.form.get('payment_method', 'Cash')
                cursor = conn.execute("""INSERT INTO sales
                    (seller,item_name,quantity,unit_price,total_price,amount_paid,change_given,payment_method,date_time)
                    VALUES (?,?,?,?,?,?,?,?,?)""",
                    (session['username'],item_name,quantity,unit_price,total,amount_paid,change,
                     payment_method,
                     datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                sale_id = cursor.lastrowid

                # ── Auto reduce stock ─────────────────────────
                if product:
                    new_stock = product['stock_quantity'] - quantity
                    conn.execute("UPDATE inventory SET stock_quantity=? WHERE product_name=?",
                                (new_stock, item_name))

                    # ── Low stock alert ───────────────────────
                    if new_stock <= product['low_stock_level']:
                        alert_msg = (f"LOW STOCK ALERT!\n{item_name}\n"
                                   f"Remaining: {new_stock} units\n"
                                   f"Please restock immediately!\n"
                                   f"-- {settings['business_name']}")
                        if settings.get('sms_enabled') and settings.get('at_api_key'):
                            send_sms(alert_msg, settings)
                        if settings.get('email_enabled') and settings.get('gmail_app_password'):
                            send_email(f"Low Stock Alert - {item_name}", alert_msg, settings)

                conn.commit()
                conn.close()

                log_activity(session['username'], 'SALE',
                           f"Sold {quantity}x {item_name} for {settings['business_currency']} {total:,.2f}")

                last_sale = {'id':sale_id,'item_name':item_name,'quantity':quantity,
                            'unit_price':unit_price,'total_price':total,'amount_paid':amount_paid,
                            'change_given':change,'date_time':datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            'seller':session['username']}
                success = f"Sale recorded! Change: {settings['business_currency']} {change:,.2f}"

                # ── Sale notifications ────────────────────────
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                sms_msg = (f"NEW SALE!\nSeller: {session['username']}\nItem: {item_name}\n"
                          f"Qty: {quantity}\nTotal: {settings['business_currency']} {total:,.2f}\n"
                          f"Paid: {settings['business_currency']} {amount_paid:,.2f}\n"
                          f"Change: {settings['business_currency']} {change:,.2f}\nTime: {now}")
                email_subject = f"New Sale - {settings['business_currency']} {total:,.2f} by {session['username']}"
                email_body = (f"New Sale!\n\nSeller: {session['username']}\nItem: {item_name}\n"
                             f"Qty: {quantity}\nUnit Price: {settings['business_currency']} {unit_price:,.2f}\n"
                             f"Total: {settings['business_currency']} {total:,.2f}\n"
                             f"Paid: {settings['business_currency']} {amount_paid:,.2f}\n"
                             f"Change: {settings['business_currency']} {change:,.2f}\n"
                             f"Time: {now}\n\n-- {settings['business_name']}")
                if settings.get('sms_enabled') and settings.get('at_api_key'):
                    send_sms(sms_msg, settings)
                if settings.get('email_enabled') and settings.get('gmail_app_password'):
                    send_email(email_subject, email_body, settings)

    conn = get_db()
    sales = conn.execute("SELECT * FROM sales WHERE seller=? ORDER BY date_time DESC",(session['username'],)).fetchall()
    products = conn.execute("SELECT * FROM inventory ORDER BY product_name ASC").fetchall()
    conn.close()
    total_earned = sum(s['total_price'] for s in sales)
    return render_template('seller.html', sales=sales, total_earned=total_earned,
                           success=success, error=error, last_sale=last_sale,
                           products=products, settings=settings, username=session['username'])

# ── RECEIPT ───────────────────────────────────────────────────
@app.route('/receipt/<int:sale_id>')
def receipt(sale_id):
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    conn = get_db()
    sale = conn.execute("SELECT * FROM sales WHERE id=?",(sale_id,)).fetchone()
    conn.close()
    settings = get_settings()
    return render_template('receipt.html', sale=dict(sale), settings=settings)

# ── OWNER ─────────────────────────────────────────────────────
@app.route('/owner')
def owner():
    if not session.get('logged_in') or session.get('role') != 'owner':
        return redirect(url_for('login'))
    conn = get_db()
    sales = conn.execute("SELECT * FROM sales ORDER BY date_time DESC").fetchall()
    users = conn.execute("SELECT username, role FROM users").fetchall()
    inventory = conn.execute("SELECT * FROM inventory ORDER BY product_name ASC").fetchall()
    activity = conn.execute("SELECT * FROM activity_log ORDER BY date_time DESC LIMIT 50").fetchall()
    conn.close()
    sales_list = [dict(s) for s in sales]
    inventory_list = [dict(i) for i in inventory]
    activity_list = [dict(a) for a in activity]
    total_revenue = sum(s['total_price'] for s in sales_list)
    total_sales = len(sales_list)
    total_items = sum(s['quantity'] for s in sales_list)
    top_seller = None
    if sales_list:
        st = {}
        for s in sales_list:
            st[s['seller']] = st.get(s['seller'],0) + s['total_price']
        top_seller = max(st, key=st.get)
    settings = get_settings()
    low_stock = get_low_stock_products()
    expiring = get_expiring_soon()

    # ── Profit calculation ────────────────────────────────────
    total_profit = 0
    for s in sales_list:
        conn2 = get_db()
        product = conn2.execute("SELECT buying_price FROM inventory WHERE product_name=?",
                               (s['item_name'],)).fetchone()
        conn2.close()
        if product:
            total_profit += (s['unit_price'] - product['buying_price']) * s['quantity']

    # ── Fast moving products ──────────────────────────────────
    item_totals = {}
    for s in sales_list:
        item_totals[s['item_name']] = item_totals.get(s['item_name'],0) + s['quantity']
    fast_movers = sorted(item_totals.items(), key=lambda x: x[1], reverse=True)[:5]

    return render_template('owner.html', sales=sales_list, users=users,
                           inventory=inventory_list, activity=activity_list,
                           total_revenue=total_revenue, total_sales=total_sales,
                           total_items=total_items, top_seller=top_seller,
                           total_profit=total_profit, fast_movers=fast_movers,
                           low_stock=low_stock, expiring=expiring,
                           settings=settings)


# ── INVENTORY PAGE ────────────────────────────────────────────
@app.route('/inventory')
def inventory():
    if not session.get('logged_in') or session.get('role') != 'owner':
        return redirect(url_for('login'))
    conn = get_db()
    inventory = conn.execute("SELECT * FROM inventory ORDER BY product_name ASC").fetchall()
    conn.close()
    settings = get_settings()
    low_stock = get_low_stock_products()
    expiring = get_expiring_soon()
    return render_template('inventory.html',
                           inventory=[dict(i) for i in inventory],
                           low_stock=low_stock,
                           expiring=expiring,
                           settings=settings)

# ── INVENTORY ROUTES ──────────────────────────────────────────
@app.route('/add_product', methods=['POST'])
def add_product():
    if not session.get('logged_in') or session.get('role') != 'owner':
        return jsonify({'success':False})
    product_name = request.form.get('product_name','').strip()
    category = request.form.get('category','General').strip()
    buying_price = float(request.form.get('buying_price', 0))
    selling_price = float(request.form.get('selling_price', 0))
    stock_quantity = int(request.form.get('stock_quantity', 0))
    low_stock_level = int(request.form.get('low_stock_level', 5))
    expiry_date = request.form.get('expiry_date','').strip()

    if not product_name:
        return jsonify({'success':False,'message':'Product name is required.'})
    try:
        conn = get_db()
        conn.execute("""INSERT INTO inventory
            (product_name,category,buying_price,selling_price,stock_quantity,low_stock_level,expiry_date,date_added)
            VALUES (?,?,?,?,?,?,?,?)""",
            (product_name, category, buying_price, selling_price,
             stock_quantity, low_stock_level,
             expiry_date if expiry_date else None,
             datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit(); conn.close()
        log_activity(session['username'], 'INVENTORY',
                    f"Added product: {product_name} (Stock: {stock_quantity})")
        return jsonify({'success':True,'message':f"'{product_name}' added to inventory!"})
    except Exception as e:
        return jsonify({'success':False,'message':f'Product already exists or error: {str(e)}'})

@app.route('/update_stock', methods=['POST'])
def update_stock():
    if not session.get('logged_in') or session.get('role') != 'owner':
        return jsonify({'success':False})
    product_id = request.form.get('product_id')
    new_quantity = int(request.form.get('stock_quantity', 0))
    conn = get_db()
    product = conn.execute("SELECT * FROM inventory WHERE id=?", (product_id,)).fetchone()
    conn.execute("UPDATE inventory SET stock_quantity=? WHERE id=?", (new_quantity, product_id))
    conn.commit(); conn.close()
    if product:
        log_activity(session['username'], 'RESTOCK',
                    f"Restocked {product['product_name']} to {new_quantity} units")
    return jsonify({'success':True,'message':'Stock updated!'})

@app.route('/delete_product', methods=['POST'])
def delete_product():
    if not session.get('logged_in') or session.get('role') != 'owner':
        return jsonify({'success':False})
    product_id = request.form.get('product_id')
    conn = get_db()
    product = conn.execute("SELECT * FROM inventory WHERE id=?", (product_id,)).fetchone()
    conn.execute("DELETE FROM inventory WHERE id=?", (product_id,))
    conn.commit(); conn.close()
    if product:
        log_activity(session['username'], 'DELETE_PRODUCT',
                    f"Deleted product: {product['product_name']}")
    return jsonify({'success':True,'message':'Product deleted!'})

@app.route('/api/products')
def get_products():
    if not session.get('logged_in'):
        return jsonify([])
    conn = get_db()
    products = conn.execute("SELECT * FROM inventory ORDER BY product_name ASC").fetchall()
    conn.close()
    return jsonify([dict(p) for p in products])

@app.route('/api/low_stock')
def api_low_stock():
    if not session.get('logged_in'):
        return jsonify([])
    return jsonify(get_low_stock_products())

# ── USER MANAGEMENT ───────────────────────────────────────────
@app.route('/add_seller', methods=['POST'])
def add_seller():
    if not session.get('logged_in') or session.get('role') != 'owner':
        return jsonify({'success':False})
    username = request.form['username'].strip()
    password = request.form['password'].strip()
    role = request.form.get('role','seller').strip()
    if not username or not password:
        return jsonify({'success':False,'message':'Please fill in both fields.'})
    try:
        conn = get_db()
        hashed = hashlib.sha256(password.encode()).hexdigest()
        conn.execute("INSERT INTO users (username,password,role) VALUES (?,?,?)",(username,hashed,role))
        conn.commit(); conn.close()
        log_activity(session['username'], 'ADD_USER', f"Added {role}: {username}")
        return jsonify({'success':True,'message':f"{role.title()} '{username}' added!"})
    except:
        return jsonify({'success':False,'message':'Username already exists.'})

# ── SETTINGS ──────────────────────────────────────────────────
@app.route('/save_settings', methods=['POST'])
def save_settings():
    if not session.get('logged_in') or session.get('role') != 'owner':
        return jsonify({'success':False})
    conn = get_db()
    conn.execute("""UPDATE settings SET
        business_name=?,business_location=?,business_currency=?,business_color=?,
        owner_phone=?,owner_email=?,at_username=?,at_api_key=?,
        gmail_address=?,gmail_app_password=?,sms_enabled=?,email_enabled=?,
        low_stock_threshold=?
        WHERE id=1""",
        (request.form.get('business_name','My Business'),
         request.form.get('business_location',''),
         request.form.get('business_currency','KSh'),
         request.form.get('business_color','#1565C0'),
         request.form.get('owner_phone',''),
         request.form.get('owner_email',''),
         request.form.get('at_username',''),
         request.form.get('at_api_key',''),
         request.form.get('gmail_address',''),
         request.form.get('gmail_app_password',''),
         1 if request.form.get('sms_enabled') else 0,
         1 if request.form.get('email_enabled') else 0,
         int(request.form.get('low_stock_threshold', 5))))
    conn.commit(); conn.close()
    return jsonify({'success':True,'message':'Settings saved!'})

@app.route('/test_sms')
def test_sms():
    if not session.get('logged_in') or session.get('role') != 'owner':
        return jsonify({'success':False})
    settings = get_settings()
    result = send_sms(f"Test SMS from {settings['business_name']}! SMS alerts working.", settings)
    return jsonify({'success':result})

@app.route('/test_email')
def test_email():
    if not session.get('logged_in') or session.get('role') != 'owner':
        return jsonify({'success':False})
    settings = get_settings()
    result, error = send_email(f"Test - {settings['business_name']}","Email alerts working!",settings)
    return jsonify({'success':result,'error':error})

# ── EXPORT ────────────────────────────────────────────────────
@app.route('/export_csv')
def export_csv():
    if not session.get('logged_in') or session.get('role') != 'owner':
        return redirect(url_for('login'))
    settings = get_settings()
    conn = get_db()
    sales = conn.execute("SELECT * FROM sales ORDER BY date_time DESC").fetchall()
    conn.close()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID','Seller','Item','Qty','Unit Price','Total','Amount Paid','Change','Date & Time'])
    for s in sales:
        writer.writerow([s['id'],s['seller'],s['item_name'],s['quantity'],
                         s['unit_price'],s['total_price'],s['amount_paid'],s['change_given'],s['date_time']])
    biz = settings.get('business_name','sales').replace(' ','-').lower()
    return Response(output.getvalue(), mimetype='text/csv',
                    headers={'Content-Disposition':f'attachment;filename={biz}-sales.csv'})

@app.route('/export_inventory_csv')
def export_inventory_csv():
    if not session.get('logged_in') or session.get('role') != 'owner':
        return redirect(url_for('login'))
    settings = get_settings()
    conn = get_db()
    inventory = conn.execute("SELECT * FROM inventory ORDER BY product_name ASC").fetchall()
    conn.close()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID','Product','Category','Buying Price','Selling Price','Stock','Low Stock Level','Expiry Date','Date Added'])
    for i in inventory:
        writer.writerow([i['id'],i['product_name'],i['category'],i['buying_price'],
                         i['selling_price'],i['stock_quantity'],i['low_stock_level'],
                         i['expiry_date'],i['date_added']])
    biz = settings.get('business_name','inventory').replace(' ','-').lower()
    return Response(output.getvalue(), mimetype='text/csv',
                    headers={'Content-Disposition':f'attachment;filename={biz}-inventory.csv'})

# ── ANALYTICS API ─────────────────────────────────────────────
@app.route('/api/sales_data')
def sales_data():
    if not session.get('logged_in'):
        return jsonify({})
    conn = get_db()
    sales = conn.execute("SELECT * FROM sales ORDER BY date_time DESC").fetchall()
    conn.close()
    sales_list = [dict(s) for s in sales]
    seller_totals = {}; daily_totals = {}; item_totals = {}
    today = datetime.now().strftime("%Y-%m-%d")
    today_revenue = 0; today_count = 0
    for s in sales_list:
        seller_totals[s['seller']] = seller_totals.get(s['seller'],0) + s['total_price']
        date = s['date_time'][:10]
        daily_totals[date] = daily_totals.get(date,0) + s['total_price']
        item_totals[s['item_name']] = item_totals.get(s['item_name'],0) + s['quantity']
        if date == today:
            today_revenue += s['total_price']
            today_count += 1
    return jsonify({'seller_totals':seller_totals,'daily_totals':daily_totals,
                    'item_totals':dict(sorted(item_totals.items(),key=lambda x:x[1],reverse=True)[:10]),
                    'today_revenue':today_revenue,'today_count':today_count})


# ── RESET PASSWORD (Owner resets for staff) ───────────────────
@app.route('/reset_password', methods=['POST'])
def reset_password():
    if not session.get('logged_in') or session.get('role') != 'owner':
        return jsonify({'success': False})
    username = request.form.get('username')
    new_password = request.form.get('new_password').strip()
    if not new_password:
        return jsonify({'success': False, 'message': 'Please enter a new password.'})
    hashed = hashlib.sha256(new_password.encode()).hexdigest()
    conn = get_db()
    conn.execute("UPDATE users SET password=? WHERE username=?", (hashed, username))
    conn.commit()
    conn.close()
    log_activity(session['username'], 'RESET_PASSWORD', f"Reset password for {username}")
    return jsonify({'success': True, 'message': f"Password reset for '{username}' successfully!"})

# ── CHANGE PASSWORD (User changes own password) ───────────────
@app.route('/change_password', methods=['POST'])
def change_password():
    if not session.get('logged_in'):
        return jsonify({'success': False})
    old_password = request.form.get('old_password').strip()
    new_password = request.form.get('new_password').strip()
    confirm_password = request.form.get('confirm_password').strip()
    if not old_password or not new_password or not confirm_password:
        return jsonify({'success': False, 'message': 'Please fill in all fields.'})
    if new_password != confirm_password:
        return jsonify({'success': False, 'message': 'New passwords do not match.'})
    if len(new_password) < 6:
        return jsonify({'success': False, 'message': 'Password must be at least 6 characters.'})
    old_hashed = hashlib.sha256(old_password.encode()).hexdigest()
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE username=? AND password=?",
                       (session['username'], old_hashed)).fetchone()
    if not user:
        conn.close()
        return jsonify({'success': False, 'message': 'Old password is incorrect.'})
    new_hashed = hashlib.sha256(new_password.encode()).hexdigest()
    conn.execute("UPDATE users SET password=? WHERE username=?",
                (new_hashed, session['username']))
    conn.commit()
    conn.close()
    log_activity(session['username'], 'CHANGE_PASSWORD', f"{session['username']} changed their password")
    return jsonify({'success': True, 'message': 'Password changed successfully!'})



# ── PAYMENT METHODS ROUTES ────────────────────────────────────

@app.route('/payment_methods')
def payment_methods():
    if not session.get('logged_in') or session.get('role') != 'owner':
        return redirect(url_for('login'))
    conn = get_db()
    methods = conn.execute("SELECT * FROM payment_methods ORDER BY id ASC").fetchall()
    conn.close()
    settings = get_settings()
    return render_template('payment_methods.html',
                           methods=[dict(m) for m in methods],
                           settings=settings)

@app.route('/add_payment_method', methods=['POST'])
def add_payment_method():
    if not session.get('logged_in') or session.get('role') != 'owner':
        return jsonify({'success': False})
    method_name = request.form.get('method_name', '').strip()
    method_type = request.form.get('method_type', '').strip()
    details = request.form.get('details', '').strip()
    if not method_name or not details:
        return jsonify({'success': False, 'message': 'Please fill in all fields.'})
    conn = get_db()
    conn.execute("INSERT INTO payment_methods (method_name, method_type, details) VALUES (?,?,?)",
                (method_name, method_type, details))
    conn.commit()
    conn.close()
    log_activity(session['username'], 'PAYMENT_METHOD', f"Added payment method: {method_name}")
    return jsonify({'success': True, 'message': f"'{method_name}' added successfully!"})

@app.route('/delete_payment_method', methods=['POST'])
def delete_payment_method():
    if not session.get('logged_in') or session.get('role') != 'owner':
        return jsonify({'success': False})
    method_id = request.form.get('method_id')
    conn = get_db()
    conn.execute("DELETE FROM payment_methods WHERE id=?", (method_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'message': 'Payment method deleted!'})

@app.route('/api/payment_methods')
def get_payment_methods():
    if not session.get('logged_in'):
        return jsonify([])
    conn = get_db()
    methods = conn.execute("SELECT * FROM payment_methods WHERE is_active=1").fetchall()
    conn.close()
    return jsonify([dict(m) for m in methods])

# ── PROFIT INTELLIGENCE ROUTES ───────────────────────────────

@app.route('/profit')
def profit():
    if not session.get('logged_in') or session.get('role') != 'owner':
        return redirect(url_for('login'))
    conn = get_db()
    sales = conn.execute("SELECT * FROM sales ORDER BY date_time DESC").fetchall()
    expenses = conn.execute("SELECT * FROM expenses ORDER BY date_time DESC").fetchall()
    inventory = conn.execute("SELECT * FROM inventory").fetchall()
    conn.close()
    settings = get_settings()
    sales_list = [dict(s) for s in sales]
    expenses_list = [dict(e) for e in expenses]
    inventory_dict = {i['product_name']: i['buying_price'] for i in inventory}

    # ── Calculate profits ─────────────────────────────────────
    today = datetime.now().strftime("%Y-%m-%d")
    this_week_start = datetime.now().strftime("%Y-%W")
    this_month = datetime.now().strftime("%Y-%m")

    daily_profit = 0
    weekly_profit = 0
    monthly_profit = 0
    total_profit = 0
    product_profits = {}

    for s in sales_list:
        buying = inventory_dict.get(s['item_name'], 0)
        profit_per_unit = s['unit_price'] - buying
        sale_profit = profit_per_unit * s['quantity']
        total_profit += sale_profit

        date = s['date_time'][:10]
        sale_week = datetime.strptime(date, "%Y-%m-%d").strftime("%Y-%W")
        sale_month = date[:7]

        if date == today:
            daily_profit += sale_profit
        if sale_week == this_week_start:
            weekly_profit += sale_profit
        if sale_month == this_month:
            monthly_profit += sale_profit

        if s['item_name'] not in product_profits:
            product_profits[s['item_name']] = {'profit': 0, 'units': 0, 'revenue': 0}
        product_profits[s['item_name']]['profit'] += sale_profit
        product_profits[s['item_name']]['units'] += s['quantity']
        product_profits[s['item_name']]['revenue'] += s['total_price']

    # Sort by profit
    top_products = sorted(product_profits.items(), key=lambda x: x[1]['profit'], reverse=True)[:10]

    # ── Expenses ──────────────────────────────────────────────
    total_expenses = sum(e['amount'] for e in expenses_list)
    monthly_expenses = sum(e['amount'] for e in expenses_list if e['date_time'][:7] == this_month)
    net_profit = total_profit - total_expenses

    # ── Business Health Score ─────────────────────────────────
    health_score = 0
    if len(sales_list) > 0: health_score += 25
    if total_profit > 0: health_score += 25
    if net_profit > 0: health_score += 25
    low_stock = get_low_stock_products()
    if len(low_stock) == 0: health_score += 25

    return render_template('profit.html',
                           settings=settings,
                           daily_profit=daily_profit,
                           weekly_profit=weekly_profit,
                           monthly_profit=monthly_profit,
                           total_profit=total_profit,
                           total_expenses=total_expenses,
                           monthly_expenses=monthly_expenses,
                           net_profit=net_profit,
                           top_products=top_products,
                           expenses=expenses_list,
                           health_score=health_score,
                           sales_count=len(sales_list))

@app.route('/add_expense', methods=['POST'])
def add_expense():
    if not session.get('logged_in') or session.get('role') != 'owner':
        return jsonify({'success': False})
    description = request.form.get('description', '').strip()
    amount = float(request.form.get('amount', 0))
    category = request.form.get('category', 'General')
    if not description or amount <= 0:
        return jsonify({'success': False, 'message': 'Please fill in all fields.'})
    conn = get_db()
    conn.execute("INSERT INTO expenses (description, amount, category, date_time) VALUES (?,?,?,?)",
                (description, amount, category, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()
    log_activity(session['username'], 'EXPENSE', f"Added expense: {description} - {amount}")
    return jsonify({'success': True, 'message': f"Expense '{description}' added!"})

@app.route('/delete_expense', methods=['POST'])
def delete_expense():
    if not session.get('logged_in') or session.get('role') != 'owner':
        return jsonify({'success': False})
    expense_id = request.form.get('expense_id')
    conn = get_db()
    conn.execute("DELETE FROM expenses WHERE id=?", (expense_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'message': 'Expense deleted!'})

@app.route('/api/profit_data')
def profit_data():
    if not session.get('logged_in'):
        return jsonify({})
    conn = get_db()
    sales = conn.execute("SELECT * FROM sales ORDER BY date_time ASC").fetchall()
    inventory = conn.execute("SELECT * FROM inventory").fetchall()
    conn.close()
    inventory_dict = {i['product_name']: i['buying_price'] for i in inventory}
    daily_profits = {}
    for s in sales:
        date = s['date_time'][:10]
        buying = inventory_dict.get(s['item_name'], 0)
        profit = (s['unit_price'] - buying) * s['quantity']
        daily_profits[date] = daily_profits.get(date, 0) + profit
    return jsonify({'daily_profits': daily_profits})

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
