import http.server
import socketserver
import sqlite3
import urllib.parse
import os
import http.cookies
import uuid
import csv
import io
from datetime import datetime
from email.parser import BytesParser
from email.policy import default

PORT = 8000
UPLOAD_DIR = 'static/uploads'

if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)

def init_db():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE,
                    email TEXT,
                    password TEXT,
                    address TEXT DEFAULT '',
                    phone TEXT DEFAULT '',
                    profile_img TEXT DEFAULT '/static/images/default_avatar.png',
                    role TEXT DEFAULT 'user'
                )''')

    try: c.execute("ALTER TABLE users ADD COLUMN address TEXT DEFAULT ''")
    except sqlite3.OperationalError: pass
    try: c.execute("ALTER TABLE users ADD COLUMN phone TEXT DEFAULT ''")
    except sqlite3.OperationalError: pass
    try: c.execute("ALTER TABLE users ADD COLUMN profile_img TEXT DEFAULT '/static/images/default_avatar.png'")
    except sqlite3.OperationalError: pass

    c.execute('''CREATE TABLE IF NOT EXISTS products (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT,
                    category TEXT,
                    description TEXT,
                    price REAL,
                    stock INTEGER,
                    image_url TEXT,
                    sold_count INTEGER DEFAULT 0
                )''')

    try: c.execute("ALTER TABLE products ADD COLUMN sold_count INTEGER DEFAULT 0")
    except sqlite3.OperationalError: pass

    c.execute('''CREATE TABLE IF NOT EXISTS banners (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT,
                    subtitle TEXT,
                    image_url TEXT
                )''')

    c.execute('''CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )''')

    c.execute('''CREATE TABLE IF NOT EXISTS cart (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    product_id INTEGER,
                    quantity INTEGER
                )''')

    c.execute('''CREATE TABLE IF NOT EXISTS orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    total_price REAL,
                    vat_price REAL DEFAULT 0,
                    net_price REAL DEFAULT 0,
                    shipping_address TEXT,
                    phone TEXT DEFAULT '',
                    status TEXT,
                    cancel_reason TEXT DEFAULT '',
                    slip_url TEXT DEFAULT '',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )''')

    c.execute('''CREATE TABLE IF NOT EXISTS order_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_id INTEGER,
                    product_id INTEGER,
                    quantity INTEGER,
                    price REAL
                )''')

    c.execute("SELECT * FROM users WHERE username = 'admin'")
    if not c.fetchone():
        c.execute("INSERT INTO users (username, email, password, role, profile_img) VALUES ('admin', 'admin@store.com', 'admin123', 'admin', '/static/images/default_avatar.png')")

    c.execute("SELECT * FROM settings WHERE key = 'qr_code_url'")
    if not c.fetchone():
        c.execute("INSERT INTO settings (key, value) VALUES ('qr_code_url', '')")

    c.execute("SELECT * FROM settings WHERE key = 'promptpay_name'")
    if not c.fetchone():
        c.execute("INSERT INTO settings (key, value) VALUES ('promptpay_name', 'นาย ภูมิภัทร ตรีบุญเมือง')")

    c.execute("SELECT * FROM settings WHERE key = 'contact_info'")
    if not c.fetchone():
        c.execute("INSERT INTO settings (key, value) VALUES ('contact_info', 'https://line.me/th')")

    c.execute("SELECT COUNT(*) FROM products")
    if c.fetchone()[0] == 0:
        products_data = [
            ('ตุ๊กตาผลโมจิ/แป้ง (Dough Plush)', 'Paramecia', 'ตุ๊กตาผล Dough โทนสีครีม-ม่วง ดีไซน์สุดน่ารัก นุ่มนิ่มน่าสะสม', 1378.30, 15, '/static/images/dough.jpg', 0),
            ('ตุ๊กตาผลจิ้งจอก (Kitsune Plush)', 'Zoan', 'ตุ๊กตาผลคิตสึเนะ สีม่วงสดใส ลายหน้าจิ้งจอกในตำนานสุดแรร์', 2022.30, 8, '/static/images/kitsune.jpg', 0),
            ('ตุ๊กตาผลมังกร (Dragon Plush)', 'Zoan', 'ตุ๊กตาผลมังกร สีเขียวพร้อมเขาสีส้มและปีกปุยนุ่มสุดอลังการ', 2129.30, 5, '/static/images/dragon.jpg', 0),
            ('ตุ๊กตาผลพระ (Buddha Plush)', 'Zoan', 'ตุ๊กตาผลพระ สีเหลืองทองออร่า ทรงลูกบาศก์สุดน่ารัก', 1273.30, 0, '/static/images/buddha.jpg', 0),
            ('ตุ๊กตาผลทีเร็กซ์ (T-Rex Plush)', 'Zoan', 'ตุ๊กตาผลไดโนเสาร์ T-Rex หัวกะโหลกพร้อมเขาและตาแดงสุดเท่', 1604.30, 10, '/static/images/t-rex.webp', 0),
            ('ตุ๊กตาผลเสือดาว (Leopard Plush)', 'Zoan', 'ตุ๊กตาผลเลโอพาร์ด ลายจุดเสือดาวสีเหลืองนวล พร้อมหางยาว', 1701.30, 12, '/static/images/tiger.jpg', 0),
            ('ตุ๊กตาผลน้ำแข็ง (Ice Plush)', 'Logia', 'ตุ๊กตาผลไอซ์ สีฟ้าสดใส ลวดลายเกล็ดน้ำแข็งพร้อมจุกสีดำ', 1059.30, 25, '/static/images/ice.png', 0)
        ]
        c.executemany("INSERT INTO products (name, category, description, price, stock, image_url, sold_count) VALUES (?, ?, ?, ?, ?, ?, ?)", products_data)

    c.execute("SELECT COUNT(*) FROM banners")
    if c.fetchone()[0] == 0:
        default_banners = [
            ('คอลเลกชันสินค้าพรีเมียม 2026', 'รวบรวมสินค้าลิขสิทธิ์แท้ จัดส่งไวทั่วประเทศ', '/static/images/banner1.jpg'),
            ('โปรโมชันพิเศษต้อนรับซีซันใหม่', 'ช้อปครบตามกำหนด รับสิทธิพิเศษและส่วนลดมากมายทันที', '/static/images/banner2.jpg')
        ]
        c.executemany("INSERT INTO banners (title, subtitle, image_url) VALUES (?, ?, ?)", default_banners)

    conn.commit()
    conn.close()

class SimpleServerHandler(http.server.SimpleHTTPRequestHandler):

    def get_cookie_user(self):
        if "Cookie" in self.headers:
            cookie = http.cookies.SimpleCookie(self.headers["Cookie"])
            if "user_id" in cookie:
                user_id = cookie["user_id"].value
                conn = sqlite3.connect('database.db')
                c = conn.cursor()
                c.execute("SELECT id, username, email, address, phone, role, profile_img FROM users WHERE id = ?", (user_id,))
                user = c.fetchone()
                conn.close()
                if user:
                    p_img = user[6] if user[6] else '/static/images/default_avatar.png'
                    return {"id": user[0], "username": user[1], "email": user[2], "address": user[3], "phone": user[4], "role": user[5], "profile_img": p_img}
        return None

    def render_template(self, filename, context={}):
        filepath = os.path.join('templates', filename)
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        for key, val in context.items():
            content = content.replace(f"{{{{ {key} }}}}", str(val))
        return content

    def do_GET(self):
        user = self.get_cookie_user()
        parsed_path = urllib.parse.urlparse(self.path)

        if self.path.startswith('/static/'):
            return super().do_GET()

        if parsed_path.path in ['/', '/shop']:
            conn = sqlite3.connect('database.db')
            c = conn.cursor()
            
            c.execute("SELECT * FROM banners")
            banners = c.fetchall()
            banner_slides = ""
            for b in banners:
                banner_slides += f'''
                <div class="slide">
                    <img src="{b[3]}" alt="{b[1]}">
                    <div class="slide-caption">
                        <h2>{b[1]}</h2>
                        <p>{b[2]}</p>
                    </div>
                </div>
                '''

            c.execute("SELECT * FROM products WHERE category = 'Paramecia'")
            paramecia = c.fetchall()
            c.execute("SELECT * FROM products WHERE category = 'Zoan'")
            zoan = c.fetchall()
            c.execute("SELECT * FROM products WHERE category = 'Logia'")
            logia = c.fetchall()

            c.execute("SELECT COUNT(*) FROM products")
            total_items_count = c.fetchone()[0] or 0

            c.execute("SELECT SUM(stock) FROM products")
            total_stock_count = c.fetchone()[0] or 0

            c.execute('''SELECT SUM(oi.quantity) 
                         FROM order_items oi 
                         JOIN orders o ON oi.order_id = o.id 
                         WHERE o.status = 'ชำระแล้ว' OR o.status = 'จัดส่งสำเร็จ' ''')
            total_sold_count = c.fetchone()[0] or 0
            
            c.execute("SELECT value FROM settings WHERE key = 'contact_info'")
            contact_res = c.fetchone()
            contact_url = contact_res[0] if contact_res else '#'

            cart_count = 0
            if user:
                c.execute("SELECT SUM(quantity) FROM cart WHERE user_id = ?", (user['id'],))
                cart_count = c.fetchone()[0] or 0
            conn.close()

            def make_cards(items):
                cards = ""
                for item in items:
                    is_out = item[5] <= 0
                    out_class = " out-of-stock" if is_out else ""
                    stock_text = f"คงเหลือ: {item[5]} ชิ้น" if not is_out else "สินค้าหมด"
                    btn_disabled = "disabled style='background: #94a3b8 !important; cursor: not-allowed; box-shadow:none;'" if is_out else ""
                    btn_label = "สินค้าหมด" if is_out else "เพิ่มเข้าตะกร้า"

                    cards += f'''
                    <div class="product-card{out_class}" data-name="{item[1].lower()}" data-category="{item[2]}" data-price="{item[4]}" data-sold="{item[7] or 0}">
                        <div>
                            <div class="img-wrapper"><img src="{item[6]}" alt="{item[1]}"></div>
                            <h3>{item[1]}</h3>
                            <p class="desc">{item[3]}</p>
                        </div>
                        <div>
                            <div class="price-box">
                                <span class="price">฿{item[4]:,.2f}</span>
                                <span class="stock">{stock_text}</span>
                            </div>
                            <form onsubmit="addToCart(event, '{item[0]}')">
                                <button type="submit" class="btn-cyan" id="btn-cart-{item[0]}" {btn_disabled}>{btn_label}</button>
                            </form>
                        </div>
                    </div>
                    '''
                return cards

            if user:
                admin_btn = '<a href="/admin" class="nav-btn nav-btn-outline" style="background: #ffffff; color: #dc143c; font-weight: bold;">หลังบ้าน (Admin)</a>' if user['role'] == 'admin' else ''
                profile_avatar = f'<img src="{user["profile_img"]}" style="width:26px; height:26px; border-radius:8px; object-fit:cover; margin-right:6px;" onerror="this.src=\'/static/images/default_avatar.png\';">'
                user_nav = f'''
                {admin_btn}
                <a href="/profile" class="nav-btn nav-btn-outline" style="display:inline-flex; align-items:center;">{profile_avatar} โปรไฟล์</a>
                <a href="/cart" class="nav-btn nav-btn-primary" id="cart-nav-badge">ตะกร้าสินค้า ({cart_count})</a>
                <a href="/logout" class="nav-btn nav-btn-outline">ออกจากระบบ</a>
                '''
            else:
                user_nav = '''
                <a href="/login" class="nav-btn nav-btn-outline">เข้าสู่ระบบ</a>
                <a href="/register" class="nav-btn nav-btn-outline">สมัครสมาชิก</a>
                <a href="/login" class="nav-btn nav-btn-primary">ตะกร้าสินค้า</a>
                '''

            context = {
                'user_nav': user_nav,
                'banner_slides': banner_slides,
                'total_items_count': f"{total_items_count:,} รายการ",
                'total_stock_count': f"{total_stock_count:,} ชิ้น",
                'total_sold_count': f"{total_sold_count:,} ชิ้น",
                'paramecia_items': make_cards(paramecia),
                'zoan_items': make_cards(zoan),
                'logia_items': make_cards(logia),
                'contact_url': contact_url
            }
            html = self.render_template('shop.html', context)
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(html.encode('utf-8'))

        elif parsed_path.path == '/login':
            html = self.render_template('login.html', {'error_block': ''})
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(html.encode('utf-8'))

        elif parsed_path.path == '/forgot-password':
            html = self.render_template('forgot_password.html', {'error_block': ''})
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(html.encode('utf-8'))

        elif parsed_path.path == '/register':
            html = self.render_template('register.html', {'error_block': ''})
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(html.encode('utf-8'))

        elif parsed_path.path == '/profile':
            if not user:
                self.redirect('/login')
                return

            conn = sqlite3.connect('database.db')
            c = conn.cursor()
            c.execute('''SELECT id, total_price, status, created_at, cancel_reason 
                         FROM orders 
                         WHERE user_id = ? 
                         ORDER BY id DESC''', (user['id'],))
            orders = c.fetchall()

            order_history_rows = ""
            for o in orders:
                reason_html = f'<br><small style="color:#ef4444;">เหตุผลที่ยกเลิก: {o[4]}</small>' if o[2] == 'ยกเลิก' and o[4] else ''
                order_history_rows += f'''
                <tr>
                    <td><strong>#{o[0]}</strong></td>
                    <td>{o[3]}</td>
                    <td>฿{o[1]:,.2f}</td>
                    <td><span class="badge">{o[2]}</span>{reason_html}</td>
                    <td><a href="/receipt?order_id={o[0]}" class="btn-cyan-sm" style="text-decoration:none;">ดูใบเสร็จ</a></td>
                </tr>
                '''
            conn.close()

            admin_btn = '<a href="/admin" class="nav-btn nav-btn-outline" style="background: #ffffff; color: #dc143c; font-weight: bold;">หลังบ้าน (Admin)</a>' if user['role'] == 'admin' else ''

            context = {
                'admin_btn': admin_btn,
                'username': user['username'],
                'email': user['email'] if user['email'] else '',
                'phone': user['phone'] if user['phone'] else '',
                'address': user['address'] if user['address'] else '',
                'profile_img': user['profile_img'],
                'order_history_rows': order_history_rows if order_history_rows else '<tr><td colspan="5" style="text-align:center;">ยังไม่มีประวัติการสั่งซื้อ</td></tr>'
            }
            html = self.render_template('profile.html', context)
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(html.encode('utf-8'))

        elif parsed_path.path == '/cart':
            if not user:
                self.redirect('/login')
                return

            conn = sqlite3.connect('database.db')
            c = conn.cursor()
            c.execute('''SELECT c.id, p.name, p.price, c.quantity, (p.price * c.quantity), p.stock, p.id 
                         FROM cart c JOIN products p ON c.product_id = p.id 
                         WHERE c.user_id = ?''', (user['id'],))
            items = c.fetchall()
            conn.close()
            
            rows = ""
            grand_total = 0
            for item in items:
                grand_total += item[4]
                rows += f'''
                <tr>
                    <td>{item[1]}</td>
                    <td>฿{item[2]:,.2f}</td>
                    <td>
                        <div style="display: flex; align-items: center; gap: 8px;">
                            <a href="/cart/update?cart_id={item[0]}&action=decrease" class="btn-qty">-</a>
                            <span>{item[3]}</span>
                            <a href="/cart/update?cart_id={item[0]}&action=increase" class="btn-qty">+</a>
                        </div>
                    </td>
                    <td>฿{item[4]:,.2f}</td>
                    <td><a href="/cart/update?cart_id={item[0]}&action=delete" style="color: #dc143c; text-decoration: none; font-weight: bold;">ลบ</a></td>
                </tr>
                '''

            checkout_btn = ""
            if grand_total > 0:
                checkout_btn = '<a href="/checkout/address" class="btn-cyan" style="text-decoration:none;">ดำเนินการสั่งซื้อ (ถัดไป) &rarr;</a>'

            subtotal = grand_total / 1.07
            vat = grand_total - subtotal

            context = {
                'username': user['username'],
                'cart_rows': rows if rows else '<tr><td colspan="5" style="text-align:center;">ยังไม่มีสินค้าในตะกร้า</td></tr>',
                'subtotal_price': f"฿{subtotal:,.2f}",
                'vat_price': f"฿{vat:,.2f}",
                'total_price': f"฿{grand_total:,.2f}",
                'checkout_btn': checkout_btn
            }
            html = self.render_template('cart.html', context)
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(html.encode('utf-8'))

        elif parsed_path.path == '/checkout/address':
            if not user:
                self.redirect('/login')
                return

            conn = sqlite3.connect('database.db')
            c = conn.cursor()
            c.execute('''SELECT p.name, p.price, c.quantity, (p.price * c.quantity)
                         FROM cart c JOIN products p ON c.product_id = p.id 
                         WHERE c.user_id = ?''', (user['id'],))
            items = c.fetchall()
            conn.close()

            if not items:
                self.redirect('/cart')
                return

            grand_total = sum(i[3] for i in items)
            subtotal = grand_total / 1.07
            vat = grand_total - subtotal

            order_summary_rows = ""
            for i in items:
                order_summary_rows += f"<tr><td>{i[0]} x {i[2]}</td><td style='text-align:right;'>฿{i[3]:,.2f}</td></tr>"

            context = {
                'username': user['username'],
                'address': user['address'] if user['address'] else '',
                'phone': user['phone'] if user['phone'] else '',
                'order_summary_rows': order_summary_rows,
                'subtotal_price': f"฿{subtotal:,.2f}",
                'vat_price': f"฿{vat:,.2f}",
                'total_price': f"฿{grand_total:,.2f}"
            }
            html = self.render_template('checkout_address.html', context)
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(html.encode('utf-8'))

        elif parsed_path.path == '/checkout/payment':
            if not user:
                self.redirect('/login')
                return

            conn = sqlite3.connect('database.db')
            c = conn.cursor()
            c.execute('''SELECT p.name, p.price, c.quantity, (p.price * c.quantity)
                         FROM cart c JOIN products p ON c.product_id = p.id 
                         WHERE c.user_id = ?''', (user['id'],))
            items = c.fetchall()

            if not items:
                conn.close()
                self.redirect('/cart')
                return

            grand_total = sum(i[3] for i in items)

            c.execute("SELECT value FROM settings WHERE key = 'qr_code_url'")
            qr_res = c.fetchone()
            qr_code_url = qr_res[0] if qr_res and qr_res[0] else ''

            c.execute("SELECT value FROM settings WHERE key = 'promptpay_name'")
            name_res = c.fetchone()
            promptpay_name = name_res[0] if name_res else 'นาย ภูมิภัทร ตรีบุญเมือง'
            conn.close()

            qr_img_tag = f'<img src="{qr_code_url}" alt="QR Code Payment" style="width: 220px; height: 220px; object-fit: contain; border-radius: 8px; border: 1px solid #cbd5e0; background: white; padding: 10px;">' if qr_code_url else '<p style="color: #e53e3e; font-size: 14px;">แอดมินยังไม่ได้อัปโหลดรูป QR Code ในหลังบ้าน</p>'

            context = {
                'username': user['username'],
                'address': user['address'],
                'phone': user['phone'],
                'total_price': f"฿{grand_total:,.2f}",
                'promptpay_name': promptpay_name,
                'qr_img_tag': qr_img_tag
            }
            html = self.render_template('checkout_payment.html', context)
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(html.encode('utf-8'))

        elif parsed_path.path == '/cart/update':
            if not user:
                self.redirect('/login')
                return
            query = urllib.parse.parse_qs(parsed_path.query)
            cart_id = query.get('cart_id', [''])[0]
            action = query.get('action', [''])[0]

            conn = sqlite3.connect('database.db')
            c = conn.cursor()
            c.execute("SELECT c.id, c.quantity, p.stock, c.product_id FROM cart c JOIN products p ON c.product_id = p.id WHERE c.id = ? AND c.user_id = ?", (cart_id, user['id']))
            cart_item = c.fetchone()

            if cart_item:
                c_id, qty, stock, p_id = cart_item
                if action == 'increase':
                    if qty < stock:
                        c.execute("UPDATE cart SET quantity = quantity + 1 WHERE id = ?", (c_id,))
                elif action == 'decrease':
                    if qty > 1:
                        c.execute("UPDATE cart SET quantity = quantity - 1 WHERE id = ?", (c_id,))
                    else:
                        c.execute("DELETE FROM cart WHERE id = ?", (c_id,))
                elif action == 'delete':
                    c.execute("DELETE FROM cart WHERE id = ?", (c_id,))
                conn.commit()
            conn.close()
            self.redirect('/cart')

        elif parsed_path.path == '/receipt':
            if not user:
                self.redirect('/login')
                return
            
            query = urllib.parse.parse_qs(parsed_path.query)
            order_id = query.get('order_id', [''])[0]

            conn = sqlite3.connect('database.db')
            c = conn.cursor()
            c.execute("SELECT id, total_price, net_price, shipping_address, phone, status, created_at, cancel_reason FROM orders WHERE id = ? AND user_id = ?", (order_id, user['id']))
            order = c.fetchone()

            if not order:
                self.redirect('/shop')
                conn.close()
                return

            c.execute('''SELECT p.name, oi.quantity, oi.price 
                         FROM order_items oi JOIN products p ON oi.product_id = p.id 
                         WHERE oi.order_id = ?''', (order_id,))
            items = c.fetchall()
            conn.close()

            rows = ""
            for item in items:
                rows += f"<tr><td>{item[0]}</td><td style='text-align:center;'>{item[1]}</td><td style='text-align:right;'>฿{item[2]*item[1]:,.2f}</td></tr>"

            grand_total = order[2] if order[2] else order[1]
            subtotal = grand_total / 1.07
            vat = grand_total - subtotal

            cancel_reason_block = f'<div style="margin-top: 10px; background:#fff5f5; color:#e53e3e; padding:10px 14px; border-radius:8px; font-size:13px; font-weight:600;">เหตุผลที่ยกเลิก: {order[7]}</div>' if order[5] == 'ยกเลิก' and order[7] else ''

            context = {
                'order_id': order[0],
                'date': order[6],
                'username': user['username'],
                'shipping_address': f"{order[3]} (เบอร์โทร: {order[4]})" if order[4] else order[3],
                'items_rows': rows,
                'subtotal_price': f"฿{subtotal:,.2f}",
                'vat_price': f"฿{vat:,.2f}",
                'total_price': f"฿{grand_total:,.2f}",
                'status': order[5],
                'cancel_reason_block': cancel_reason_block
            }
            html = self.render_template('receipt.html', context)
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(html.encode('utf-8'))

        elif parsed_path.path == '/admin/export-orders':
            if not user or user['role'] != 'admin':
                self.redirect('/login')
                return

            conn = sqlite3.connect('database.db')
            c = conn.cursor()
            c.execute('''SELECT o.id, u.username, u.email, COALESCE(o.net_price, o.total_price), o.status, o.created_at, o.shipping_address, o.phone 
                         FROM orders o JOIN users u ON o.user_id = u.id ORDER BY o.id DESC''')
            orders = c.fetchall()
            conn.close()

            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(['Order ID', 'Username', 'Email', 'Total Price', 'Status', 'Date', 'Address', 'Phone'])
            for row in orders:
                writer.writerow(row)

            self.send_response(200)
            self.send_header('Content-Type', 'text/csv; charset=utf-8-sig')
            self.send_header('Content-Disposition', 'attachment; filename=orders_export.csv')
            self.end_headers()
            self.wfile.write(output.getvalue().encode('utf-8-sig'))

        elif parsed_path.path == '/admin':
            if not user or user['role'] != 'admin':
                self.redirect('/login')
                return

            conn = sqlite3.connect('database.db')
            c = conn.cursor()

            now = datetime.now()
            today_str = now.strftime('%Y-%m-%d')
            month_str = now.strftime('%Y-%m')
            year_str = now.strftime('%Y')

            c.execute("SELECT SUM(COALESCE(net_price, total_price)) FROM orders WHERE (status = 'ชำระแล้ว' OR status = 'จัดส่งสำเร็จ') AND DATE(created_at) = ?", (today_str,))
            daily_sales = c.fetchone()[0] or 0.0

            c.execute("SELECT SUM(COALESCE(net_price, total_price)) FROM orders WHERE (status = 'ชำระแล้ว' OR status = 'จัดส่งสำเร็จ') AND strftime('%Y-%m', created_at) = ?", (month_str,))
            monthly_sales = c.fetchone()[0] or 0.0

            c.execute("SELECT SUM(COALESCE(net_price, total_price)) FROM orders WHERE (status = 'ชำระแล้ว' OR status = 'จัดส่งสำเร็จ') AND strftime('%Y', created_at) = ?", (year_str,))
            yearly_sales = c.fetchone()[0] or 0.0

            c.execute('''SELECT p.name, SUM(oi.quantity) as total_qty 
                         FROM order_items oi 
                         JOIN products p ON oi.product_id = p.id 
                         JOIN orders o ON oi.order_id = o.id
                         WHERE o.status = 'ชำระแล้ว' OR o.status = 'จัดส่งสำเร็จ'
                         GROUP BY p.id 
                         ORDER BY total_qty DESC''')
            top_products = c.fetchall()

            top_product_name = "ยังไม่มีข้อมูล"
            top_product_qty = 0
            if top_products:
                top_product_name = top_products[0][0]
                top_product_qty = top_products[0][1]

            c.execute("SELECT value FROM settings WHERE key = 'qr_code_url'")
            qr_res = c.fetchone()
            qr_code_url = qr_res[0] if qr_res and qr_res[0] else ''

            c.execute("SELECT value FROM settings WHERE key = 'promptpay_name'")
            name_res = c.fetchone()
            promptpay_name = name_res[0] if name_res else ''

            c.execute("SELECT value FROM settings WHERE key = 'contact_info'")
            contact_res = c.fetchone()
            contact_info = contact_res[0] if contact_res else ''

            c.execute("SELECT id, username, email, phone FROM users WHERE role = 'user' ORDER BY id DESC")
            all_users = c.fetchall()
            user_rows = ""
            for u in all_users:
                user_rows += f'''
                <tr>
                    <td>#{u[0]}</td>
                    <td><strong>{u[1]}</strong></td>
                    <td>{u[2]}</td>
                    <td>{u[3] or '-'}</td>
                </tr>
                '''

            c.execute("SELECT * FROM banners")
            banners = c.fetchall()
            banner_rows = ""
            for b in banners:
                banner_rows += f'''
                <tr>
                    <td>#{b[0]}</td>
                    <td><img src="{b[3]}" style="width: 90px; height: 45px; object-fit: cover; border-radius: 6px; border:1px solid #e2e8f0;"></td>
                    <td><input type="text" id="banner-title-{b[0]}" value="{b[1]}" style="width:100%; padding: 6px; border-radius:6px; border:1px solid #cbd5e1;" required></td>
                    <td><input type="text" id="banner-sub-{b[0]}" value="{b[2]}" style="width:100%; padding: 6px; border-radius:6px; border:1px solid #cbd5e1;"></td>
                    <td><input type="text" id="banner-img-{b[0]}" value="{b[3]}" style="width:100%; padding: 6px; border-radius:6px; border:1px solid #cbd5e1;" required></td>
                    <td>
                        <button type="button" class="btn-cyan-sm" onclick="updateBanner('{b[0]}')">บันทึก</button>
                        <a href="/admin/delete-banner?id={b[0]}" style="color:#ef4444; font-size:12px; margin-left:6px; text-decoration:none;" onclick="return confirm('ยืนยันลบแบนเนอร์?')">ลบ</a>
                    </td>
                </tr>
                '''

            query_params = urllib.parse.parse_qs(parsed_path.query)
            
            p_page = int(query_params.get('p', [1])[0])
            p_per = 10
            p_offset = (p_page - 1) * p_per

            c.execute("SELECT COUNT(*) FROM products")
            total_products = c.fetchone()[0]
            total_prod_pages = (total_products + p_per - 1) // p_per

            c.execute("SELECT * FROM products LIMIT ? OFFSET ?", (p_per, p_offset))
            products = c.fetchall()
            prod_rows = ""
            for p in products:
                prod_rows += f'''
                <tr id="product-row-{p[0]}">
                    <td>{p[0]}</td>
                    <td><img src="{p[6]}" style="width: 45px; height: 45px; object-fit: cover; border-radius: 6px;"></td>
                    <td><input type="text" id="name-{p[0]}" value="{p[1]}" style="width: 100%; padding: 6px; border-radius:6px; border:1px solid #cbd5e1;" required></td>
                    <td>
                        <select id="category-{p[0]}" style="padding: 6px; width: 100%; border-radius:6px; border:1px solid #cbd5e1;">
                            <option value="Paramecia" {'selected' if p[2]=='Paramecia' else ''}>Paramecia</option>
                            <option value="Zoan" {'selected' if p[2]=='Zoan' else ''}>Zoan</option>
                            <option value="Logia" {'selected' if p[2]=='Logia' else ''}>Logia</option>
                        </select>
                    </td>
                    <td><input type="text" id="desc-{p[0]}" value="{p[3]}" style="width: 100%; padding: 6px; border-radius:6px; border:1px solid #cbd5e1;" required></td>
                    <td><input type="number" step="0.01" id="price-{p[0]}" value="{p[4]}" style="width: 90px; padding: 6px; border-radius:6px; border:1px solid #cbd5e1;" required></td>
                    <td><input type="number" id="stock-{p[0]}" value="{p[5]}" style="width: 70px; padding: 6px; border-radius:6px; border:1px solid #cbd5e1;" required></td>
                    <td><input type="text" id="image-{p[0]}" value="{p[6]}" style="width: 100%; padding: 6px; border-radius:6px; border:1px solid #cbd5e1;" required></td>
                    <td>
                        <button type="button" class="btn-cyan-sm" onclick="updateProduct('{p[0]}')">บันทึก</button>
                        <a href="/admin/delete-product?id={p[0]}" style="color:#ef4444; font-size:12px; margin-left:6px; text-decoration:none;" onclick="return confirm('ยืนยันลบสินค้านี้?')">ลบ</a>
                    </td>
                </tr>
                '''

            today_p = int(query_params.get('today_p', [1])[0])
            orders_p = int(query_params.get('orders_p', [1])[0])

            def make_page_link(p_num, orders_num, today_num):
                return f"/admin?p={p_num}&orders_p={orders_num}&today_p={today_num}"

            prod_pagination_html = ""
            if total_prod_pages > 1:
                prod_pagination_html = '<div style="display: flex; justify-content: center; gap: 8px; margin-top: 15px;">'
                for i in range(1, total_prod_pages + 1):
                    active_cls = " active" if i == p_page else ""
                    prod_pagination_html += f'<a href="{make_page_link(i, orders_p, today_p)}" onclick="saveScroll()" class="pagination-link{active_cls}">{i}</a>'
                prod_pagination_html += '</div>'

            today_per = 5
            today_offset = (today_p - 1) * today_per

            c.execute("SELECT COUNT(*) FROM orders WHERE DATE(created_at) = ?", (today_str,))
            total_today_orders = c.fetchone()[0]
            total_today_pages = (total_today_orders + today_per - 1) // today_per

            c.execute('''SELECT o.id, u.username, u.email, COALESCE(o.net_price, o.total_price), o.status, o.created_at, o.slip_url, o.shipping_address, o.phone, o.cancel_reason 
                         FROM orders o JOIN users u ON o.user_id = u.id 
                         WHERE DATE(o.created_at) = ? 
                         ORDER BY o.id DESC LIMIT ? OFFSET ?''', (today_str, today_per, today_offset))
            today_orders = c.fetchall()

            def build_order_rows(order_list):
                rows_html = ""
                for o in order_list:
                    c.execute('''SELECT p.name, oi.quantity 
                                 FROM order_items oi 
                                 JOIN products p ON oi.product_id = p.id 
                                 WHERE oi.order_id = ?''', (o[0],))
                    items_in_order = c.fetchall()
                    
                    items_html = "<ul style='padding-left:14px; font-size:12px; color:#dc143c; font-weight:600;'>"
                    for item in items_in_order:
                        items_html += f"<li>{item[0]} <span style='color:#e11d48;'>x {item[1]}</span></li>"
                    items_html += "</ul>"

                    slip_btn = f'<a href="{o[6]}" target="_blank"><img src="{o[6]}" style="width:45px; height:45px; object-fit:cover; border-radius:6px; border:1px solid #cbd5e0;" title="คลิกดูรูปใหญ่"></a>' if o[6] else '<span style="color:#a0aec0; font-size:12px;">ไม่พบสลีป</span>'
                    is_cancelled = o[4] == 'ยกเลิก'
                    reason_val = o[9] if o[9] else ''
                    
                    rows_html += f'''
                    <tr id="order-row-{o[0]}" style="{'background: #fff1f2;' if is_cancelled else ''}">
                        <td><strong>#{o[0]}</strong></td>
                        <td>
                            <strong>{o[1]}</strong><br>
                            <small style="color:#64748b;">{o[2]}</small>
                        </td>
                        <td>{items_html}</td>
                        <td><strong style="color:#059669;">฿{o[3]:,.2f}</strong></td>
                        <td>
                            <textarea id="order-addr-{o[0]}" rows="2" style="width:100%; padding:4px; font-size:11px; font-family:'Prompt'; border-radius:4px; border:1px solid #cbd5e1;">{o[7]}</textarea>
                            <input type="text" id="order-phone-{o[0]}" value="{o[8]}" placeholder="เบอร์โทร" style="width:100%; padding:4px; font-size:11px; margin-top:3px; font-family:'Prompt'; border-radius:4px; border:1px solid #cbd5e1;">
                        </td>
                        <td><div style="text-align:center;">{slip_btn}</div></td>
                        <td>
                            <select id="order-status-{o[0]}" onchange="toggleCancelReason('{o[0]}')" style="font-size: 12px; padding: 4px; width:100%; border-radius:4px; border:1px solid #cbd5e1;">
                                <option value="รอตรวจสลิป" {'selected' if o[4]=='รอตรวจสลิป' else ''}>รอตรวจสลิป</option>
                                <option value="ชำระแล้ว" {'selected' if o[4]=='ชำระแล้ว' else ''}>ชำระแล้ว</option>
                                <option value="อยู่ระหว่างการจัดส่ง" {'selected' if o[4]=='อยู่ระหว่างการจัดส่ง' else ''}>อยู่ระหว่างการจัดส่ง</option>
                                <option value="จัดส่งสำเร็จ" {'selected' if o[4]=='จัดส่งสำเร็จ' else ''}>จัดส่งสำเร็จ</option>
                                <option value="ยกเลิก" {'selected' if is_cancelled else ''}>ยกเลิก (คืนสต็อก)</option>
                            </select>
                            <div id="cancel-reason-box-{o[0]}" style="margin-top:4px; display: {'block' if is_cancelled else 'none'};">
                                <input type="text" id="order-cancel-reason-{o[0]}" value="{reason_val}" placeholder="ระบุเหตุผลที่ยกเลิก..." style="width:100%; padding:4px; font-size:11px; border:1px solid #f87171; border-radius:4px;">
                            </div>
                        </td>
                        <td style="font-size:12px; color:#64748b;">{o[5]}</td>
                        <td>
                            <button type="button" class="btn-cyan-sm" onclick="updateOrder('{o[0]}')">บันทึก</button>
                        </td>
                    </tr>
                    '''
                return rows_html

            today_order_rows = build_order_rows(today_orders)
            today_pagination_html = ""
            if total_today_pages > 1:
                today_pagination_html = '<div style="display: flex; justify-content: center; gap: 8px; margin-top: 15px;">'
                for i in range(1, total_today_pages + 1):
                    active_cls = " active" if i == today_p else ""
                    today_pagination_html += f'<a href="{make_page_link(p_page, orders_p, i)}" onclick="saveScroll()" class="pagination-link{active_cls}">{i}</a>'
                today_pagination_html += '</div>'

            orders_per = 10
            orders_offset = (orders_p - 1) * orders_per

            c.execute("SELECT COUNT(*) FROM orders")
            total_orders = c.fetchone()[0]
            total_orders_pages = (total_orders + orders_per - 1) // orders_per

            c.execute('''SELECT o.id, u.username, u.email, COALESCE(o.net_price, o.total_price), o.status, o.created_at, o.slip_url, o.shipping_address, o.phone, o.cancel_reason 
                         FROM orders o JOIN users u ON o.user_id = u.id 
                         ORDER BY o.id DESC LIMIT ? OFFSET ?''', (orders_per, orders_offset))
            all_orders = c.fetchall()

            order_rows = build_order_rows(all_orders)
            orders_pagination_html = ""
            if total_orders_pages > 1:
                orders_pagination_html = '<div style="display: flex; justify-content: center; gap: 8px; margin-top: 15px;">'
                for i in range(1, total_orders_pages + 1):
                    active_cls = " active" if i == orders_p else ""
                    orders_pagination_html += f'<a href="{make_page_link(p_page, i, today_p)}" onclick="saveScroll()" class="pagination-link{active_cls}">{i}</a>'
                orders_pagination_html += '</div>'

            conn.close()

            context = {
                'daily_sales': f"฿{daily_sales:,.2f}",
                'monthly_sales': f"฿{monthly_sales:,.2f}",
                'yearly_sales': f"฿{yearly_sales:,.2f}",
                'top_product_name': top_product_name,
                'top_product_qty': top_product_qty,
                'qr_code_url': qr_code_url,
                'promptpay_name': promptpay_name,
                'contact_info': contact_info,
                'user_rows': user_rows if user_rows else '<tr><td colspan="4" style="text-align:center;">ยังไม่มีสมาชิกทั่วไป</td></tr>',
                'banner_rows': banner_rows,
                'product_rows': prod_rows,
                'pagination_html': prod_pagination_html,
                'today_order_rows': today_order_rows if today_order_rows else '<tr><td colspan="9" style="text-align:center; padding:20px; color:#94a3b8;">ยังไม่มีรายการสั่งซื้อของวันนี้</td></tr>',
                'today_pagination_html': today_pagination_html,
                'order_rows': order_rows,
                'orders_pagination_html': orders_pagination_html
            }
            html = self.render_template('admin.html', context)
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(html.encode('utf-8'))

        elif parsed_path.path == '/admin/delete-banner':
            user = self.get_cookie_user()
            if user and user['role'] == 'admin':
                query = urllib.parse.parse_qs(parsed_path.query)
                banner_id = query.get('id', [''])[0]
                conn = sqlite3.connect('database.db')
                c = conn.cursor()
                c.execute("DELETE FROM banners WHERE id = ?", (banner_id,))
                conn.commit()
                conn.close()
            self.redirect('/admin')

        elif parsed_path.path == '/admin/delete-product':
            user = self.get_cookie_user()
            if user and user['role'] == 'admin':
                query = urllib.parse.parse_qs(parsed_path.query)
                prod_id = query.get('id', [''])[0]
                conn = sqlite3.connect('database.db')
                c = conn.cursor()
                c.execute("DELETE FROM products WHERE id = ?", (prod_id,))
                conn.commit()
                conn.close()
            self.redirect('/admin')

        elif parsed_path.path == '/logout':
            self.send_response(302)
            self.send_header('Location', '/shop')
            self.send_header('Set-Cookie', 'user_id=; Max-Age=0')
            self.end_headers()

        else:
            self.send_error(404, "Page Not Found")

    def do_POST(self):
        content_type = self.headers.get('Content-Type', '')
        
        if 'multipart/form-data' in content_type:
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            msg = BytesParser(policy=default).parsebytes(
                f"Content-Type: {content_type}\n\n".encode('utf-8') + body
            )

            if self.path == '/admin/add-banner':
                user = self.get_cookie_user()
                if not user or user['role'] != 'admin':
                    self.redirect('/login')
                    return

                title = ''
                subtitle = ''
                image_url = ''

                for part in msg.walk():
                    if part.get_content_disposition() == 'form-data':
                        p_name = part.get_param('name', header='content-disposition')
                        if p_name == 'title':
                            title = part.get_payload(decode=True).decode('utf-8', errors='ignore').strip()
                        elif p_name == 'subtitle':
                            subtitle = part.get_payload(decode=True).decode('utf-8', errors='ignore').strip()
                        elif p_name == 'banner_file':
                            filename = part.get_filename()
                            if filename:
                                ext = os.path.splitext(filename)[1]
                                new_filename = f"banner_{uuid.uuid4()}{ext}"
                                filepath = os.path.join(UPLOAD_DIR, new_filename)
                                with open(filepath, 'wb') as f:
                                    f.write(part.get_payload(decode=True))
                                image_url = f"/{filepath}"

                if title and image_url:
                    conn = sqlite3.connect('database.db')
                    c = conn.cursor()
                    c.execute("INSERT INTO banners (title, subtitle, image_url) VALUES (?, ?, ?)", (title, subtitle, image_url))
                    conn.commit()
                    conn.close()

                self.redirect('/admin')
                return

            if self.path == '/update-profile':
                user = self.get_cookie_user()
                if not user:
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    self.wfile.write(b'{"status": "unauthorized"}')
                    return

                username = ''
                email = ''
                address = ''
                phone = ''
                profile_img_url = ''

                for part in msg.walk():
                    if part.get_content_disposition() == 'form-data':
                        p_name = part.get_param('name', header='content-disposition')
                        if p_name == 'username':
                            username = part.get_payload(decode=True).decode('utf-8', errors='ignore').strip()
                        elif p_name == 'email':
                            email = part.get_payload(decode=True).decode('utf-8', errors='ignore').strip()
                        elif p_name == 'address':
                            address = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                        elif p_name == 'phone':
                            phone = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                        elif p_name == 'profile_img':
                            filename = part.get_filename()
                            if filename:
                                ext = os.path.splitext(filename)[1]
                                new_filename = f"avatar_{uuid.uuid4()}{ext}"
                                filepath = os.path.join(UPLOAD_DIR, new_filename)
                                with open(filepath, 'wb') as f:
                                    f.write(part.get_payload(decode=True))
                                profile_img_url = f"/{filepath}"

                conn = sqlite3.connect('database.db')
                c = conn.cursor()
                
                if username and username != user['username']:
                    c.execute("SELECT id FROM users WHERE username = ?", (username,))
                    if c.fetchone():
                        conn.close()
                        self.send_response(200)
                        self.send_header('Content-type', 'application/json')
                        self.end_headers()
                        self.wfile.write(b'{"status": "error", "message": "\\u0e0a\\u0e37\\u0e48\\u0e2d\\u0e1c\\u0e31\\u0e49\\u0e43\\u0e0a\\u0e49\\u0e19\\u0e35\\u0e49\\u0e16\\u0e32\\u0e01\\u0e43\\u0e0a\\u0e49\\u0e41\\u0e25\\u0e49\\u0e27"}')
                        return

                final_username = username if username else user['username']
                final_email = email if email else user['email']

                if profile_img_url:
                    c.execute("UPDATE users SET username = ?, email = ?, address = ?, phone = ?, profile_img = ? WHERE id = ?", (final_username, final_email, address, phone, profile_img_url, user['id']))
                else:
                    c.execute("UPDATE users SET username = ?, email = ?, address = ?, phone = ? WHERE id = ?", (final_username, final_email, address, phone, user['id']))
                
                conn.commit()
                conn.close()

                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(b'{"status": "success"}')
                return

            if self.path == '/admin/update-qr-file':
                user = self.get_cookie_user()
                if not user or user['role'] != 'admin':
                    self.redirect('/login')
                    return

                qr_url = ''
                promptpay_name = ''
                
                for part in msg.walk():
                    if part.get_content_disposition() == 'form-data':
                        name = part.get_param('name', header='content-disposition')
                        if name == 'promptpay_name':
                            promptpay_name = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                        elif name == 'qr_file':
                            filename = part.get_filename()
                            if filename:
                                ext = os.path.splitext(filename)[1]
                                new_filename = f"qr_{uuid.uuid4()}{ext}"
                                filepath = os.path.join(UPLOAD_DIR, new_filename)
                                with open(filepath, 'wb') as f:
                                    f.write(part.get_payload(decode=True))
                                qr_url = f"/{filepath}"

                conn = sqlite3.connect('database.db')
                c = conn.cursor()
                if qr_url:
                    c.execute("UPDATE settings SET value = ? WHERE key = 'qr_code_url'", (qr_url,))
                if promptpay_name:
                    c.execute("UPDATE settings SET value = ? WHERE key = 'promptpay_name'", (promptpay_name,))
                conn.commit()
                conn.close()
                self.redirect('/admin')
                return

            if self.path == '/checkout/confirm':
                user = self.get_cookie_user()
                if not user:
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    self.wfile.write(b'{"status": "unauthorized"}')
                    return

                slip_url = ''
                for part in msg.walk():
                    if part.get_content_disposition() == 'form-data' and part.get_param('name', header='content-disposition') == 'slip_file':
                        filename = part.get_filename()
                        if filename:
                            ext = os.path.splitext(filename)[1]
                            new_filename = f"{uuid.uuid4()}{ext}"
                            filepath = os.path.join(UPLOAD_DIR, new_filename)
                            with open(filepath, 'wb') as f:
                                f.write(part.get_payload(decode=True))
                            slip_url = f"/{filepath}"
                            break

                conn = sqlite3.connect('database.db')
                c = conn.cursor()
                c.execute("SELECT address, phone FROM users WHERE id = ?", (user['id'],))
                u_res = c.fetchone()
                user_address = u_res[0] if u_res and u_res[0] else ''
                user_phone = u_res[1] if u_res and u_res[1] else ''

                c.execute('''SELECT c.product_id, c.quantity, p.price, p.stock 
                             FROM cart c JOIN products p ON c.product_id = p.id 
                             WHERE c.user_id = ?''', (user['id'],))
                cart_items = c.fetchall()

                if not cart_items:
                    conn.close()
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    self.wfile.write(b'{"status": "empty_cart"}')
                    return

                grand_total = sum(item[1] * item[2] for item in cart_items)

                c.execute("INSERT INTO orders (user_id, total_price, vat_price, net_price, shipping_address, phone, status, slip_url) VALUES (?, ?, 0, ?, ?, ?, 'รอตรวจสลิป', ?)", 
                          (user['id'], grand_total, grand_total, user_address, user_phone, slip_url))
                order_id = c.lastrowid

                for item in cart_items:
                    p_id, qty, price, stock = item
                    c.execute("INSERT INTO order_items (order_id, product_id, quantity, price) VALUES (?, ?, ?, ?)", (order_id, p_id, qty, price))
                    c.execute("UPDATE products SET stock = stock - ?, sold_count = sold_count + ? WHERE id = ?", (qty, qty, p_id))

                c.execute("DELETE FROM cart WHERE user_id = ?", (user['id'],))
                conn.commit()
                conn.close()

                res_data = f'{{"status": "success", "order_id": {order_id}}}'
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(res_data.encode('utf-8'))
                return

        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length).decode('utf-8')
        params = urllib.parse.parse_qs(post_data)

        if self.path == '/login':
            username = params.get('username', [''])[0]
            password = params.get('password', [''])[0]

            conn = sqlite3.connect('database.db')
            c = conn.cursor()
            c.execute("SELECT id, role FROM users WHERE username = ? AND password = ?", (username, password))
            user = c.fetchone()
            conn.close()

            if user:
                user_id, role = user[0], user[1]
                self.send_response(302)
                if role == 'admin':
                    self.send_header('Location', '/admin')
                else:
                    self.send_header('Location', '/shop')
                self.send_header('Set-Cookie', f'user_id={user_id}; Path=/')
                self.end_headers()
            else:
                html = self.render_template('login.html', {'error_block': '<div class="error-msg">ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง</div>'})
                self.send_response(200)
                self.send_header('Content-type', 'text/html; charset=utf-8')
                self.end_headers()
                self.wfile.write(html.encode('utf-8'))

        # ระบบรีเซ็ตรหัสผ่านอย่างง่าย (ไม่ต้องใช้ OTP)
        elif self.path == '/forgot-password':
            username = params.get('username', [''])[0].strip()
            email = params.get('email', [''])[0].strip()
            new_password = params.get('new_password', [''])[0]

            has_upper = any(c.isupper() for c in new_password)
            has_lower = any(c.islower() for c in new_password)
            has_digit = any(c.isdigit() for c in new_password)

            if len(new_password) < 6 or len(new_password) > 20 or not (has_upper and has_lower and has_digit):
                html = self.render_template('forgot_password.html', {'error_block': '<div class="error-msg">รหัสผ่านต้องมีความยาว 6-20 ตัวอักษร และมีพิมพ์ใหญ่ พิมพ์เล็ก ตัวเลข</div>'})
                self.send_response(200)
                self.send_header('Content-type', 'text/html; charset=utf-8')
                self.end_headers()
                self.wfile.write(html.encode('utf-8'))
                return

            conn = sqlite3.connect('database.db')
            c = conn.cursor()
            c.execute("SELECT id FROM users WHERE username = ? AND email = ?", (username, email))
            user = c.fetchone()

            if user:
                c.execute("UPDATE users SET password = ? WHERE id = ?", (new_password, user[0]))
                conn.commit()
                conn.close()
                html = self.render_template('login.html', {'error_block': '<div style="background:#f0fdf4; color:#166534; padding:10px; border-radius:8px; font-size:13px; margin-bottom:15px; text-align:center; border:1px solid #bbf7d0;">เปลี่ยนรหัสผ่านสำเร็จแล้ว! กรุณาเข้าสู่ระบบด้วยรหัสผ่านใหม่</div>'})
                self.send_response(200)
                self.send_header('Content-type', 'text/html; charset=utf-8')
                self.end_headers()
                self.wfile.write(html.encode('utf-8'))
            else:
                conn.close()
                html = self.render_template('forgot_password.html', {'error_block': '<div class="error-msg">ไม่พบข้อมูลชื่อผู้ใช้และอีเมลนี้ในระบบ</div>'})
                self.send_response(200)
                self.send_header('Content-type', 'text/html; charset=utf-8')
                self.end_headers()
                self.wfile.write(html.encode('utf-8'))

        elif self.path == '/register':
            email = params.get('email', [''])[0].strip()
            username = params.get('username', [''])[0].strip()
            password = params.get('password', [''])[0]
            confirm_password = params.get('confirm_password', [''])[0]

            if not email.endswith('@gmail.com'):
                html = self.render_template('register.html', {'error_block': '<div class="error-msg">อีเมลต้องลงท้ายด้วย @gmail.com เท่านั้น</div>'})
                self.send_response(200)
                self.send_header('Content-type', 'text/html; charset=utf-8')
                self.end_headers()
                self.wfile.write(html.encode('utf-8'))
                return

            if len(password) < 6 or len(password) > 20:
                html = self.render_template('register.html', {'error_block': '<div class="error-msg">รหัสผ่านต้องมีความยาวระหว่าง 6 ถึง 20 ตัวอักษร</div>'})
                self.send_response(200)
                self.send_header('Content-type', 'text/html; charset=utf-8')
                self.end_headers()
                self.wfile.write(html.encode('utf-8'))
                return

            has_upper = any(c.isupper() for c in password)
            has_lower = any(c.islower() for c in password)
            has_digit = any(c.isdigit() for c in password)

            if not (has_upper and has_lower and has_digit):
                html = self.render_template('register.html', {'error_block': '<div class="error-msg">รหัสผ่านต้องประกอบด้วย ตัวอักษรพิมพ์ใหญ่ พิมพ์เล็ก และตัวเลข อย่างน้อยอย่างละ 1 ตัว</div>'})
                self.send_response(200)
                self.send_header('Content-type', 'text/html; charset=utf-8')
                self.end_headers()
                self.wfile.write(html.encode('utf-8'))
                return

            if password != confirm_password:
                html = self.render_template('register.html', {'error_block': '<div class="error-msg">รหัสผ่านและการยืนยันรหัสผ่านไม่ตรงกัน</div>'})
                self.send_response(200)
                self.send_header('Content-type', 'text/html; charset=utf-8')
                self.end_headers()
                self.wfile.write(html.encode('utf-8'))
                return

            try:
                conn = sqlite3.connect('database.db')
                c = conn.cursor()
                c.execute("INSERT INTO users (username, email, password, role) VALUES (?, ?, ?, 'user')", (username, email, password))
                conn.commit()
                conn.close()
                self.send_response(302)
                self.send_header('Location', '/login')
                self.end_headers()
            except sqlite3.IntegrityError:
                conn.close()
                html = self.render_template('register.html', {'error_block': '<div class="error-msg">ชื่อผู้ใช้นี้ถูกใช้งานในระบบแล้ว</div>'})
                self.send_response(200)
                self.send_header('Content-type', 'text/html; charset=utf-8')
                self.end_headers()
                self.wfile.write(html.encode('utf-8'))

        elif self.path == '/checkout/save-address':
            user = self.get_cookie_user()
            if not user:
                self.redirect('/login')
                return

            address = params.get('address', [''])[0]
            phone = params.get('phone', [''])[0]
            conn = sqlite3.connect('database.db')
            c = conn.cursor()
            c.execute("UPDATE users SET address = ?, phone = ? WHERE id = ?", (address, phone, user['id']))
            conn.commit()
            conn.close()
            self.redirect('/checkout/payment')

        elif self.path == '/admin/update-contact':
            user = self.get_cookie_user()
            if user and user['role'] == 'admin':
                contact_info = params.get('contact_info', [''])[0]
                conn = sqlite3.connect('database.db')
                c = conn.cursor()
                c.execute("UPDATE settings SET value = ? WHERE key = 'contact_info'", (contact_info,))
                conn.commit()
                conn.close()
            self.redirect('/admin')

        elif self.path == '/add-to-cart':
            user = self.get_cookie_user()
            if not user:
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(b'{"status": "unauthorized"}')
                return

            product_id = params.get('product_id', [''])[0]
            conn = sqlite3.connect('database.db')
            c = conn.cursor()
            c.execute("SELECT stock, name, price, image_url FROM products WHERE id = ?", (product_id,))
            prod = c.fetchone()
            if not prod or prod[0] <= 0:
                conn.close()
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(b'{"status": "out_of_stock", "message": "\\u0e2a\\u0e34\\u0e19\\u0e04\\u0e49\\u0e32\\u0e2b\\u0e21\\u0e14"}')
                return

            max_stock = prod[0]
            c.execute("SELECT id, quantity FROM cart WHERE user_id = ? AND product_id = ?", (user['id'], product_id))
            item = c.fetchone()
            
            if item:
                current_qty = item[1]
                if current_qty < max_stock:
                    c.execute("UPDATE cart SET quantity = quantity + 1 WHERE id = ?", (item[0],))
                else:
                    conn.close()
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    self.wfile.write(b'{"status": "limit_reached", "message": "\\u0e2a\\u0e34\\u0e19\\u0e04\\u0e49\\u0e32\\u0e42\\u0e19\\u0e2a\\u0e15\\u0e4Action\\u0e21\\u0e35\\u0e08\\u0e33\\u0e19\\u0e27\\u0e19\\u0e08\\u0e33\\u0e01\\u0e31\\u0e14"}')
                    return
            else:
                c.execute("INSERT INTO cart (user_id, product_id, quantity) VALUES (?, ?, 1)", (user['id'], product_id))
            
            c.execute("SELECT SUM(quantity) FROM cart WHERE user_id = ?", (user['id'],))
            total_count = c.fetchone()[0] or 0
            conn.commit()
            conn.close()

            response_payload = f'''{{
                "status": "success", 
                "cart_count": {total_count},
                "product_name": "{prod[1]}",
                "product_price": "฿{prod[2]:,.2f}",
                "product_img": "{prod[3]}"
            }}'''

            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(response_payload.encode('utf-8'))

        elif self.path == '/admin/update-banner-inline':
            user = self.get_cookie_user()
            if user and user['role'] == 'admin':
                banner_id = params.get('banner_id', [''])[0]
                title = params.get('title', [''])[0]
                subtitle = params.get('subtitle', [''])[0]
                image_url = params.get('image_url', [''])[0]

                conn = sqlite3.connect('database.db')
                c = conn.cursor()
                c.execute("UPDATE banners SET title = ?, subtitle = ?, image_url = ? WHERE id = ?", (title, subtitle, image_url, banner_id))
                conn.commit()
                conn.close()
                
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(b'{"status": "success"}')
                return

        elif self.path == '/admin/update-product-inline':
            user = self.get_cookie_user()
            if user and user['role'] == 'admin':
                product_id = params.get('product_id', [''])[0]
                name = params.get('name', [''])[0]
                category = params.get('category', ['Paramecia'])[0]
                description = params.get('description', [''])[0]
                price = params.get('price', ['0'])[0]
                stock = params.get('stock', ['0'])[0]
                image_url = params.get('image_url', [''])[0]
                
                conn = sqlite3.connect('database.db')
                c = conn.cursor()
                c.execute('''UPDATE products 
                             SET name = ?, category = ?, description = ?, price = ?, stock = ?, image_url = ? 
                             WHERE id = ?''', (name, category, description, price, stock, image_url, product_id))
                conn.commit()
                conn.close()
                
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(b'{"status": "success"}')
                return

        elif self.path == '/admin/add-product':
            user = self.get_cookie_user()
            if user and user['role'] == 'admin':
                name = params.get('name', [''])[0]
                category = params.get('category', ['Paramecia'])[0]
                description = params.get('description', [''])[0]
                price = params.get('price', ['0'])[0]
                stock = params.get('stock', ['0'])[0]
                image_url = params.get('image_url', [''])[0]

                conn = sqlite3.connect('database.db')
                c = conn.cursor()
                c.execute('''INSERT INTO products (name, category, description, price, stock, image_url) 
                             VALUES (?, ?, ?, ?, ?, ?)''', (name, category, description, price, stock, image_url))
                conn.commit()
                conn.close()
            self.redirect('/admin')

        elif self.path == '/admin/update-order-inline':
            user = self.get_cookie_user()
            if user and user['role'] == 'admin':
                order_id = params.get('order_id', [''])[0]
                shipping_address = params.get('shipping_address', [''])[0]
                phone = params.get('phone', [''])[0]
                status = params.get('status', [''])[0]
                cancel_reason = params.get('cancel_reason', [''])[0]

                conn = sqlite3.connect('database.db')
                c = conn.cursor()
                
                c.execute("SELECT status, user_id FROM orders WHERE id = ?", (order_id,))
                old_order = c.fetchone()
                
                if old_order:
                    old_status, order_user_id = old_order
                    c.execute("UPDATE orders SET shipping_address = ?, phone = ?, status = ?, cancel_reason = ? WHERE id = ?", (shipping_address, phone, status, cancel_reason, order_id))

                    if old_status != 'ยกเลิก' and status == 'ยกเลิก':
                        c.execute("SELECT product_id, quantity FROM order_items WHERE order_id = ?", (order_id,))
                        items_to_restore = c.fetchall()
                        for p_id, qty in items_to_restore:
                            c.execute("UPDATE products SET stock = stock + ?, sold_count = CASE WHEN sold_count >= ? THEN sold_count - ? ELSE 0 END WHERE id = ?", (qty, qty, qty, p_id))

                conn.commit()
                conn.close()

                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(b'{"status": "success"}')
                return

    def redirect(self, location):
        self.send_response(302)
        self.send_header('Location', location)
        self.end_headers()

if __name__ == '__main__':
    init_db()
    server = socketserver.TCPServer(('', PORT), SimpleServerHandler)
    print(f"Server runs at: http://localhost:{PORT}")
    server.serve_forever()