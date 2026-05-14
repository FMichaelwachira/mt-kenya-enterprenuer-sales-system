from flask import Flask, render_template, request, redirect, url_for, session, jsonify, Response
import sqlite3
import hashlib
from datetime import datetime
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
        email_enabled INTEGER DEFAULT 0
    )''')
    c.execute("SELECT COUNT(*) FROM settings")
    if c.fetchone()[0] == 0:
        c.execute("""INSERT INTO settings
            (business_name,business_location,business_currency,business_color,
             owner_phone,owner_email,at_username,at_api_key,
             gmail_address,gmail_app_password,sms_enabled,email_enabled)
            VALUES ('My Business','','KSh','#1565C0','','','','','','',0,0)""")
    for col in [
        "ALTER TABLE sales ADD COLUMN amount_paid REAL NOT NULL DEFAULT 0",
        "ALTER TABLE sales ADD COLUMN change_given REAL NOT NULL DEFAULT 0",
        "ALTER TABLE settings ADD COLUMN business_name TEXT DEFAULT 'My Business'",
        "ALTER TABLE settings ADD COLUMN business_location TEXT DEFAULT ''",
        "ALTER TABLE settings ADD COLUMN business_currency TEXT DEFAULT 'KSh'",
        "ALTER TABLE settings ADD COLUMN business_color TEXT DEFAULT '#1565C0'"
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
            return redirect(url_for('owner' if user['role']=='owner' else 'seller'))
        else:
            error = "Wrong username or password. Try again."
    return render_template('login.html', error=error, settings=settings)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

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
            conn = get_db()
            cursor = conn.execute("""INSERT INTO sales
                (seller,item_name,quantity,unit_price,total_price,amount_paid,change_given,date_time)
                VALUES (?,?,?,?,?,?,?,?)""",
                (session['username'],item_name,quantity,unit_price,total,amount_paid,change,
                 datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            sale_id = cursor.lastrowid
            conn.commit()
            conn.close()
            last_sale = {'id':sale_id,'item_name':item_name,'quantity':quantity,
                        'unit_price':unit_price,'total_price':total,'amount_paid':amount_paid,
                        'change_given':change,'date_time':datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        'seller':session['username']}
            success = f"Sale recorded! Change: {settings['business_currency']} {change:,.2f}"
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
    conn.close()
    total_earned = sum(s['total_price'] for s in sales)
    return render_template('seller.html', sales=sales, total_earned=total_earned,
                           success=success, error=error, last_sale=last_sale,
                           settings=settings, username=session['username'])

@app.route('/receipt/<int:sale_id>')
def receipt(sale_id):
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    conn = get_db()
    sale = conn.execute("SELECT * FROM sales WHERE id=?",(sale_id,)).fetchone()
    conn.close()
    settings = get_settings()
    return render_template('receipt.html', sale=dict(sale), settings=settings)

@app.route('/owner')
def owner():
    if not session.get('logged_in') or session.get('role') != 'owner':
        return redirect(url_for('login'))
    conn = get_db()
    sales = conn.execute("SELECT * FROM sales ORDER BY date_time DESC").fetchall()
    users = conn.execute("SELECT username, role FROM users").fetchall()
    conn.close()
    sales_list = [dict(s) for s in sales]
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
    return render_template('owner.html', sales=sales_list, users=users,
                           total_revenue=total_revenue, total_sales=total_sales,
                           total_items=total_items, top_seller=top_seller, settings=settings)

@app.route('/add_seller', methods=['POST'])
def add_seller():
    if not session.get('logged_in') or session.get('role') != 'owner':
        return jsonify({'success':False})
    username = request.form['username'].strip()
    password = request.form['password'].strip()
    if not username or not password:
        return jsonify({'success':False,'message':'Please fill in both fields.'})
    try:
        conn = get_db()
        hashed = hashlib.sha256(password.encode()).hexdigest()
        conn.execute("INSERT INTO users (username,password,role) VALUES (?,?,?)",(username,hashed,'seller'))
        conn.commit(); conn.close()
        return jsonify({'success':True,'message':f"Seller '{username}' added!"})
    except:
        return jsonify({'success':False,'message':'Username already exists.'})

@app.route('/save_settings', methods=['POST'])
def save_settings():
    if not session.get('logged_in') or session.get('role') != 'owner':
        return jsonify({'success':False})
    conn = get_db()
    conn.execute("""UPDATE settings SET
        business_name=?,business_location=?,business_currency=?,business_color=?,
        owner_phone=?,owner_email=?,at_username=?,at_api_key=?,
        gmail_address=?,gmail_app_password=?,sms_enabled=?,email_enabled=?
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
         1 if request.form.get('email_enabled') else 0))
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

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
