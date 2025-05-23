import streamlit as st
import sqlite3
import bcrypt
import pandas as pd
import uuid
from datetime import datetime, timedelta

# Database setup
def init_db():
    conn = sqlite3.connect('orders.db')
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        username TEXT UNIQUE,
        password TEXT,
        is_admin BOOLEAN
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS orders (
        id TEXT PRIMARY KEY,
        user_id TEXT,
        business_name TEXT,
        email TEXT,
        phone TEXT,
        address TEXT,
        created_at TEXT,
        archived BOOLEAN DEFAULT 0,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS services (
        id TEXT PRIMARY KEY,
        order_id TEXT,
        name TEXT,
        stage TEXT,
        is_template BOOLEAN,
        template_services TEXT,
        FOREIGN KEY(order_id) REFERENCES orders(id)
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS stages (
        id TEXT PRIMARY KEY,
        name TEXT,
        position INTEGER
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS services_list (
        id TEXT PRIMARY KEY,
        name TEXT
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS custom_fields (
        id TEXT PRIMARY KEY,
        name TEXT
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS password_resets (
        id TEXT PRIMARY KEY,
        user_id TEXT,
        temp_password TEXT,
        requested_at TEXT,
        approved BOOLEAN,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS changes (
        id TEXT PRIMARY KEY,
        order_id TEXT,
        user_id TEXT,
        description TEXT,
        timestamp TEXT,
        FOREIGN KEY(order_id) REFERENCES orders(id),
        FOREIGN KEY(user_id) REFERENCES users(id)
    )''')
    
    c.execute("SELECT COUNT(*) FROM stages")
    if c.fetchone()[0] == 0:
        default_stages = [("To Do", 1), ("In Progress", 2), ("Done", 3)]
        c.executemany("INSERT INTO stages (id, name, position) VALUES (?, ?, ?)", 
                     [(str(uuid.uuid4()), name, pos) for name, pos in default_stages])
    
    c.execute("SELECT COUNT(*) FROM services_list")
    if c.fetchone()[0] == 0:
        default_services = [("Research",), ("Design",), ("Development",)]
        c.executemany("INSERT INTO services_list (id, name) VALUES (?, ?)", 
                     [(str(uuid.uuid4()), name) for name in default_services])
    
    c.execute("SELECT COUNT(*) FROM users WHERE username = ?", ('chadillac',))
    if c.fetchone()[0] == 0:
        hashed = bcrypt.hashpw('roostersgrin'.encode('utf-8'), bcrypt.gensalt())
        c.execute("INSERT INTO users (id, username, password, is_admin) VALUES (?, ?, ?, ?)",
                 (str(uuid.uuid4()), 'chadillac', hashed, True))
    
    conn.commit()
    conn.close()

# Helper functions
def check_login(username, password):
    conn = sqlite3.connect('orders.db')
    c = conn.cursor()
    c.execute("SELECT id, password, is_admin FROM users WHERE username = ?", (username,))
    user = c.fetchone()
    conn.close()
    if user and bcrypt.checkpw(password.encode('utf-8'), user[1]):
        return {'id': user[0], 'username': username, 'is_admin': user[2]}
    return None

def get_stages():
    conn = sqlite3.connect('orders.db')
    c = conn.cursor()
    c.execute("SELECT id, name, position FROM stages ORDER BY position")
    stages = c.fetchall()
    conn.close()
    return stages

def get_user_orders(user_id, is_admin=False, include_archived=False):
    conn = sqlite3.connect('orders.db')
    c = conn.cursor()
    if is_admin and include_archived:
        c.execute("SELECT * FROM orders")
    elif is_admin:
        c.execute("SELECT * FROM orders WHERE archived = 0")
    else:
        c.execute("SELECT * FROM orders WHERE user_id = ? AND archived = 0", (user_id,))
    orders = c.fetchall()
    conn.close()
    return orders

def get_all_users():
    conn = sqlite3.connect('orders.db')
    c = conn.cursor()
    c.execute("SELECT id, username FROM users")
    users = c.fetchall()
    conn.close()
    return users

def get_orders_for_user(user_id):
    conn = sqlite3.connect('orders.db')
    c = conn.cursor()
    c.execute("SELECT * FROM orders WHERE user_id = ? AND archived = 0", (user_id,))
    orders = c.fetchall()
    conn.close()
    return orders

def get_all_active_orders():
    conn = sqlite3.connect('orders.db')
    c = conn.cursor()
    c.execute("SELECT o.*, u.username FROM orders o JOIN users u ON o.user_id = u.id WHERE o.archived = 0")
    orders = c.fetchall()
    conn.close()
    return orders

def get_order_services(order_id):
    conn = sqlite3.connect('orders.db')
    c = conn.cursor()
    c.execute("SELECT id, name, stage, is_template, template_services FROM services WHERE order_id = ?", (order_id,))
    services = c.fetchall()
    conn.close()
    return services

def get_order_stage(order_id):
    conn = sqlite3.connect('orders.db')
    c = conn.cursor()
    c.execute("SELECT s.stage, st.position FROM services s JOIN stages st ON s.stage = st.id WHERE s.order_id = ? ORDER BY st.position DESC LIMIT 1", (order_id,))
    result = c.fetchone()
    conn.close()
    return result[0] if result else get_stages()[0][0]

def get_order_progress(order_id):
    services = get_order_services(order_id)
    if not services:
        return 0
    stages = get_stages()
    stage_positions = {stage[1]: stage[2] for stage in stages}
    total_stages = max(stage_positions.values())
    total_position = 0
    for service in services:
        stage_name = service[2]
        total_position += stage_positions.get(stage_name, 1)
    avg_position = total_position / len(services)
    progress = (avg_position / total_stages) * 100
    return round(progress, 2)

def get_services_list():
    conn = sqlite3.connect('orders.db')
    c = conn.cursor()
    c.execute("SELECT id, name FROM services_list")
    services = c.fetchall()
    conn.close()
    return services

def get_templates():
    conn = sqlite3.connect('orders.db')
    c = conn.cursor()
    c.execute("SELECT id, name, template_services FROM services WHERE is_template = ?", (True,))
    templates = c.fetchall()
    conn.close()
    return templates

def add_custom_field(field_name):
    conn = sqlite3.connect('orders.db')
    c = conn.cursor()
    c.execute("INSERT INTO custom_fields (id, name) VALUES (?, ?)", (str(uuid.uuid4()), field_name))
    conn.commit()
    conn.close()

def request_password_reset(user_id):
    conn = sqlite3.connect('orders.db')
    c = conn.cursor()
    temp_password = str(uuid.uuid4())[:8]
    c.execute("INSERT INTO password_resets (id, user_id, temp_password, requested_at, approved) VALUES (?, ?, ?, ?, ?)",
             (str(uuid.uuid4()), user_id, temp_password, datetime.now().isoformat(), False))
    conn.commit()
    conn.close()
    return temp_password

def approve_password_reset(reset_id, user_id):
    conn = sqlite3.connect('orders.db')
    c = conn.cursor()
    c.execute("SELECT temp_password FROM password_resets WHERE id = ?", (reset_id,))
    temp_password = c.fetchone()[0]
    hashed = bcrypt.hashpw(temp_password.encode('utf-8'), bcrypt.gensalt())
    c.execute("UPDATE users SET password = ? WHERE id = ?", (hashed, user_id))
    c.execute("UPDATE password_resets SET approved = ? WHERE id = ?", (True, reset_id))
    conn.commit()
    conn.close()

def log_change(order_id, user_id, description):
    conn = sqlite3.connect('orders.db')
    c = conn.cursor()
    c.execute("INSERT INTO changes (id, order_id, user_id, description, timestamp) VALUES (?, ?, ?, ?, ?)",
             (str(uuid.uuid4()), order_id, user_id, description, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def get_days_since_last_change(order_id):
    conn = sqlite3.connect('orders.db')
    c = conn.cursor()
    c.execute("SELECT timestamp FROM changes WHERE order_id = ? ORDER BY timestamp DESC LIMIT 1", (order_id,))
    last_change = c.fetchone()
    conn.close()
    if last_change:
        last_change_time = datetime.fromisoformat(last_change[0])
        days_diff = (datetime.now() - last_change_time).days
        return days_diff
    return None

def get_order_changes(order_id):
    conn = sqlite3.connect('orders.db')
    c = conn.cursor()
    c.execute("SELECT description, timestamp FROM changes WHERE order_id = ? ORDER BY timestamp DESC", (order_id,))
    changes = c.fetchall()
    conn.close()
    return changes

def archive_order(order_id, user_id):
    conn = sqlite3.connect('orders.db')
    c = conn.cursor()
    c.execute("UPDATE orders SET archived = 1 WHERE id = ?", (order_id,))
    log_change(order_id, user_id, "Order archived")
    conn.commit()
    conn.close()

def restore_order(order_id, user_id):
    conn = sqlite3.connect('orders.db')
    c = conn.cursor()
    c.execute("UPDATE orders SET archived = 0 WHERE id = ?", (order_id,))
    log_change(order_id, user_id, "Order restored")
    conn.commit()
    conn.close()

def add_service_to_order(order_id, user_id, service_id, template_id=None):
    conn = sqlite3.connect('orders.db')
    c = conn.cursor()
    c.execute("SELECT name FROM services_list WHERE id = ?", (service_id,))
    service_name = c.fetchone()[0]
    template_services = ""
    if template_id:
        c.execute("SELECT template_services FROM services WHERE id = ?", (template_id,))
        template_services = c.fetchone()[0]
        c.execute("INSERT INTO services (id, order_id, name, stage, is_template, template_services) VALUES (?, ?, ?, ?, ?, ?)",
                 (str(uuid.uuid4()), order_id, service_name, get_stages()[0][1], True, template_services))
    else:
        c.execute("INSERT INTO services (id, order_id, name, stage, is_template) VALUES (?, ?, ?, ?, ?)",
                 (str(uuid.uuid4()), order_id, service_name, get_stages()[0][1], False))
    log_change(order_id, user_id, f"Service {service_name} added")
    conn.commit()
    conn.close()

# Streamlit app
st.set_page_config(page_title="Order Tracking App", layout="wide")

# Initialize database
init_db()

# Session state for authentication
if 'user' not in st.session_state:
    st.session_state.user = None

# Inject modernized Tailwind CSS and custom styles
st.markdown("""
    <link href="https://cdn.jsdelivr.net/npm/tailwindcss@2.2.19/dist/tailwind.min.css" rel="stylesheet">
    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;700&display=swap" rel="stylesheet">
    <style>
        body {
            font-family: 'Poppins', sans-serif;
        }
        .sidebar {
            background-color: #1E3A8A;
        }
        .card {
            transition: all 0.2s ease-in-out;
        }
        .card:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.1);
        }
        input, select {
            border: 1px solid #D1D5DB;
            border-radius: 0.375rem;
            padding: 0.5rem;
            transition: all 0.2s ease-in-out;
        }
        input:focus, select:focus {
            outline: none;
            border-color: #3B82F6;
            box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.3);
        }
        button {
            transition: all 0.2s ease-in-out;
        }
    </style>
""", unsafe_allow_html=True)

# Login page
if not st.session_state.user:
    st.markdown('<div class="flex justify-center items-center min-h-screen bg-gray-100">', unsafe_allow_html=True)
    st.markdown('<div class="bg-white p-8 rounded-xl shadow-md w-full max-w-md">', unsafe_allow_html=True)
    st.markdown('<h1 class="text-2xl font-bold text-gray-800 mb-6 text-center">Login</h1>', unsafe_allow_html=True)
    with st.form("login_form"):
        username = st.text_input("Username", placeholder="Enter your username")
        password = st.text_input("Password", type="password", placeholder="Enter your password")
        login_button = st.form_submit_button("Login", help="Login with your credentials")
        if login_button:
            user = check_login(username, password)
            if user:
                st.session_state.user = user
                st.success("Logged in successfully!")
                st.rerun()
            else:
                st.error("Invalid username or password")
    
    st.markdown('<h2 class="text-lg font-semibold text-gray-700 mt-6 mb-2">Reset Password</h2>', unsafe_allow_html=True)
    with st.form("reset_request_form"):
        reset_username = st.text_input("Enter your username to request a password reset", placeholder="Username")
        reset_button = st.form_submit_button("Request Password Reset")
        if reset_button:
            conn = sqlite3.connect('orders.db')
            c = conn.cursor()
            c.execute("SELECT id FROM users WHERE username = ?", (reset_username,))
            user = c.fetchone()
            conn.close()
            if user:
                temp_password = request_password_reset(user[0])
                st.success(f"Password reset requested. Your temporary password is: {temp_password}. Await admin approval.")
            else:
                st.error("Username not found")
    st.markdown('</div></div>', unsafe_allow_html=True)
else:
    user_id = st.session_state.user['id']
    username = st.session_state.user['username']
    is_admin = st.session_state.user['is_admin']
    
    # Sidebar
    sidebar_html = """
        <div class="flex min-h-screen">
            <div class="w-64 sidebar text-white p-6">
                <h2 class="text-2xl font-bold mb-8">Order Tracker</h2>
                <nav>
                    <a href="#" class="block py-2 px-4 rounded hover:bg-blue-700" onclick="document.getElementById('page').value='dashboard';document.getElementById('nav-form').submit();">Dashboard</a>
                    <a href="#" class="block py-2 px-4 rounded hover:bg-blue-700" onclick="document.getElementById('page').value='orders';document.getElementById('nav-form').submit();">Orders</a>
    """
    if is_admin:
        sidebar_html += """
                    <a href="#" class="block py-2 px-4 rounded hover:bg-blue-700" onclick="document.getElementById('page').value='admin';document.getElementById('nav-form').submit();">Admin Controls</a>
        """
        if username == 'chadillac':
            sidebar_html += """
                    <a href="#" class="block py-2 px-4 rounded hover:bg-blue-700" onclick="document.getElementById('page').value='admin-dashboard';document.getElementById('nav-form').submit();">Admin Dashboard</a>
            """
    sidebar_html += """
                    <a href="#" class="block py-2 px-4 rounded hover:bg-blue-700 mt-4" onclick="document.getElementById('page').value='logout';document.getElementById('nav-form').submit();">Logout</a>
                </nav>
                <form id="nav-form" style="display:none;">
                    <input type="hidden" id="page" name="page" value="">
                </form>
            </div>
            <div class="flex-1 p-8 bg-gray-100">
    """
    st.markdown(sidebar_html, unsafe_allow_html=True)

    # Navigation logic
    if 'page' not in st.session_state:
        st.session_state.page = 'dashboard'

    page = st.session_state.page
    if st.query_params.get("page"):
        page = st.query_params.get("page")[0]
        st.session_state.page = page

    if page == 'logout':
        st.session_state.user = None
        st.rerun()

    # Dashboard Page
    if page == 'dashboard':
        st.markdown('<h1 class="text-3xl font-bold text-gray-800 mb-6">Dashboard</h1>', unsafe_allow_html=True)
        orders = get_user_orders(user_id, is_admin)
        active_orders = len(orders)
        avg_days = sum([d for d in [get_days_since_last_change(o[0]) for o in orders] if d is not None]) / (active_orders or 1)
        st.markdown(f'<p class="text-gray-600 mb-6">Active Orders: {active_orders} | Avg. Days Since Last Change: {avg_days:.1f}</p>', unsafe_allow_html=True)
        
        # Order Overview Section
        st.markdown('<h2 class="text-xl font-semibold text-gray-700 mb-4">Order Overview</h2>', unsafe_allow_html=True)
        st.markdown('<div class="bg-white rounded-xl shadow-md overflow-x-auto mb-8 card">', unsafe_allow_html=True)
        st.markdown('<table class="min-w-full divide-y divide-gray-200">', unsafe_allow_html=True)
        st.markdown('<thead class="bg-gray-50"><tr><th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Order</th><th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Total Services</th><th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Progress</th></tr></thead>', unsafe_allow_html=True)
        st.markdown('<tbody class="bg-white divide-y divide-gray-200">', unsafe_allow_html=True)
        for order in orders:
            order_id = order[0]
            business_name = order[2]
            services = get_order_services(order_id)
            total_services = len(services)
            progress = get_order_progress(order_id)
            st.markdown(f'<tr><td class="px-6 py-4 whitespace-nowrap"><div class="text-sm font-medium text-gray-900">{business_name}</div></td>', unsafe_allow_html=True)
            st.markdown(f'<td class="px-6 py-4 whitespace-nowrap"><div class="text-sm text-gray-500">{total_services}</div></td>', unsafe_allow_html=True)
            st.markdown(f'<td class="px-6 py-4 whitespace-nowrap"><div class="w-64 bg-gray-200 rounded-full h-2.5"><div class="bg-gradient-to-r from-blue-500 to-blue-600 h-2.5 rounded-full" style="width: {progress}%"></div></div><span class="ml-2 text-sm text-gray-500">{progress}%</span></td></tr>', unsafe_allow_html=True)
        st.markdown('</tbody></table></div>', unsafe_allow_html=True)

        # Detailed Dashboard
        stages = get_stages()
        orders_by_stage = {stage[1]: [] for stage in stages}
        for order in orders:
            order_id = order[0]
            stage_name = get_order_stage(order_id)
            orders_by_stage[stage_name].append(order)
        
        for stage_name in orders_by_stage:
            if orders_by_stage[stage_name]:
                stage_color = "bg-gray-200" if stage_name == "To Do" else "bg-blue-100" if stage_name == "In Progress" else "bg-green-100"
                st.markdown(f'<div class="mb-8"><h2 class="text-xl font-semibold text-gray-700 mb-4">{stage_name}</h2>', unsafe_allow_html=True)
                st.markdown('<div class="bg-white rounded-xl shadow-md overflow-x-auto card">', unsafe_allow_html=True)
                st.markdown('<table class="min-w-full divide-y divide-gray-200">', unsafe_allow_html=True)
                st.markdown('<thead class="bg-gray-50"><tr><th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Order</th><th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Services</th><th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Days Since Last Change</th><th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th><th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th></tr></thead>', unsafe_allow_html=True)
                st.markdown('<tbody class="bg-white divide-y divide-gray-200">', unsafe_allow_html=True)
                for order in orders_by_stage[stage_name]:
                    order_id, _, business_name, email, phone, address, created_at, archived = order
                    services = get_order_services(order_id)
                    service_list = ", ".join([s[1] for s in services]) or "No services"
                    for s in services:
                        if s[3]:  # is_template
                            service_list += f" ({s[4].replace('\n', ', ')})"
                    days_since = get_days_since_last_change(order_id)
                    current_stage = get_order_stage(order_id)
                    st.markdown(f'<tr><td class="px-6 py-4 whitespace-nowrap"><div class="text-sm font-medium text-gray-900">{business_name}</div></td>', unsafe_allow_html=True)
                    st.markdown(f'<td class="px-6 py-4 whitespace-nowrap"><div class="text-sm text-gray-500">{service_list}</div></td>', unsafe_allow_html=True)
                    st.markdown(f'<td class="px-6 py-4 whitespace-nowrap"><div class="text-sm text-gray-500">{days_since if days_since is not None else "No changes"}</div></td>', unsafe_allow_html=True)
                    st.markdown(f'<td class="px-6 py-4 whitespace-nowrap"><div class="inline-block"><select class="border rounded p-1 {stage_color}" onchange="this.form.submit()" name="stage_{order_id}">', unsafe_allow_html=True)
                    for s in stages:
                        selected = "selected" if s[1] == current_stage else ""
                        st.markdown(f'<option value="{s[1]}" {selected}>{s[1]}</option>', unsafe_allow_html=True)
                    st.markdown('</select></div></td>', unsafe_allow_html=True)
                    st.markdown(f'<td class="px-6 py-4 whitespace-nowrap"><button class="px-3 py-1 bg-gradient-to-r from-blue-600 to-blue-700 text-white rounded hover:from-blue-700 hover:to-blue-800" onclick="document.getElementById(\'archive_{order_id}\').click()">Archive</button><input type="hidden" id="archive_{order_id}" name="archive_{order_id}"></td></tr>', unsafe_allow_html=True)
                    if st.query_params.get(f"stage_{order_id}"):
                        new_stage = st.query_params.get(f"stage_{order_id}")[0]
                        conn = sqlite3.connect('orders.db')
                        c = conn.cursor()
                        for service in services:
                            c.execute("UPDATE services SET stage = ? WHERE order_id = ?", (new_stage, order_id))
                        log_change(order_id, user_id, f"Order moved to {new_stage}")
                        conn.commit()
                        conn.close()
                        st.rerun()
                    if st.query_params.get(f"archive_{order_id}"):
                        archive_order(order_id, user_id)
                        st.rerun()
                st.markdown('</tbody></table></div></div>', unsafe_allow_html=True)

    # Orders Page
    elif page == 'orders':
        st.markdown('<h1 class="text-3xl font-bold text-gray-800 mb-6">Orders</h1>', unsafe_allow_html=True)
        
        # Create New Order
        st.markdown('<div class="bg-white p-8 rounded-xl shadow-md mb-8 card">', unsafe_allow_html=True)
        st.markdown('<h2 class="text-xl font-semibold text-gray-700 mb-4">Create New Order</h2>', unsafe_allow_html=True)
        with st.form("new_order_form"):
            business_name = st.text_input("Business Name", placeholder="Enter business name")
            email = st.text_input("Email", placeholder="Enter email")
            phone = st.text_input("Phone", placeholder="Enter phone number")
            address = st.text_input("Address", placeholder="Enter address")
            conn = sqlite3.connect('orders.db')
            c = conn.cursor()
            c.execute("SELECT name FROM custom_fields")
            custom_fields = c.fetchall()
            conn.close()
            custom_field_values = {}
            for field in custom_fields:
                custom_field_values[field[0]] = st.text_input(field[0], placeholder=f"Enter {field[0]}")
            if st.form_submit_button("Create Order", help="Create a new order with the provided details"):
                conn = sqlite3.connect('orders.db')
                c = conn.cursor()
                order_id = str(uuid.uuid4())
                c.execute("INSERT INTO orders (id, user_id, business_name, email, phone, address, created_at, archived) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                         (order_id, user_id, business_name, email, phone, address, datetime.now().isoformat(), False))
                log_change(order_id, user_id, "Order created")
                conn.commit()
                conn.close()
                st.success("Order created!")
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Add Service from List
        st.markdown('<div class="bg-white p-8 rounded-xl shadow-md mb-8 card">', unsafe_allow_html=True)
        st.markdown('<h2 class="text-xl font-semibold text-gray-700 mb-4">Add Service to Order</h2>', unsafe_allow_html=True)
        with st.form("add_service_form"):
            orders = get_user_orders(user_id, is_admin)
            order_id = st.selectbox("Select Order", options=[o[0] for o in orders], format_func=lambda x: [o[2] for o in orders if o[0] == x][0])
            services = get_services_list()
            service_id = st.selectbox("Select Service", options=[s[0] for s in services], format_func=lambda x: [s[1] for s in services if s[0] == x][0])
            templates = get_templates()
            template_id = st.selectbox("Select Template (Optional)", options=[t[0] for t in templates] + [None], format_func=lambda x: [t[1] for t in templates if t[0] == x][0] if x else "None")
            if st.form_submit_button("Add Service", help="Add a service to the selected order"):
                add_service_to_order(order_id, user_id, service_id, template_id)
                st.success("Service added!")
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Existing Orders
        st.markdown('<div class="bg-white p-8 rounded-xl shadow-md card">', unsafe_allow_html=True)
        st.markdown('<h2 class="text-xl font-semibold text-gray-700 mb-4">Existing Orders</h2>', unsafe_allow_html=True)
        for order in get_user_orders(user_id, is_admin):
            order_id, _, business_name, email, phone, address, created_at, archived = order
            with st.expander(f"Order: {business_name} (Created: {created_at})"):
                st.markdown(f'<p class="text-gray-600">Email: {email}, Phone: {phone}, Address: {address}</p>', unsafe_allow_html=True)
                conn = sqlite3.connect('orders.db')
                c = conn.cursor()
                c.execute("SELECT name FROM custom_fields")
                for field in c.fetchall():
                    st.markdown(f'<p class="text-gray-600">{field[0]}: Not implemented in this version</p>', unsafe_allow_html=True)
                conn.close()
                
                days_since = get_days_since_last_change(order_id)
                st.markdown(f'<p class="text-gray-600">Days since last change: {days_since if days_since is not None else "No changes yet"}</p>', unsafe_allow_html=True)
                
                st.markdown('<h4 class="text-md font-medium text-gray-700 mt-4">Change Log</h4>', unsafe_allow_html=True)
                changes = get_order_changes(order_id)
                for change in changes:
                    st.markdown(f'<p class="text-gray-600">{change[1]}: {change[0]}</p>', unsafe_allow_html=True)
                
                if not archived:
                    if st.button(f"Archive Order: {business_name}", key=f"archive_{order_id}", help="Archive this order"):
                        archive_order(order_id, user_id)
                        st.success(f"Order {business_name} archived!")
                        st.rerun()
                
                st.markdown('<h4 class="text-md font-medium text-gray-700 mt-4">Add Service</h4>', unsafe_allow_html=True)
                with st.form(f"add_service_{order_id}"):
                    services = get_services_list()
                    service_id = st.selectbox("Select Service", options=[s[0] for s in services], format_func=lambda x: [s[1] for s in services if s[0] == x][0])
                    templates = get_templates()
                    template_id = st.selectbox("Select Template (Optional)", options=[t[0] for t in templates] + [None], format_func=lambda x: [t[1] for t in templates if t[0] == x][0] if x else "None")
                    if st.form_submit_button("Add Service", help="Add a service to this order"):
                        add_service_to_order(order_id, user_id, service_id, template_id)
                        st.success("Service added!")
        st.markdown('</div>', unsafe_allow_html=True)

    # Admin Controls Page
    elif page == 'admin' and is_admin:
        st.markdown('<h1 class="text-3xl font-bold text-gray-800 mb-6">Admin Controls</h1>', unsafe_allow_html=True)
        
        st.markdown('<div class="bg-white p-8 rounded-xl shadow-md mb-8 card">', unsafe_allow_html=True)
        st.markdown('<h2 class="text-xl font-semibold text-gray-700 mb-4">Manage Users</h2>', unsafe_allow_html=True)
        with st.form("add_user_form"):
            new_username = st.text_input("New Username", placeholder="Enter new username")
            new_password = st.text_input("New Password", type="password", placeholder="Enter new password")
            if st.form_submit_button("Add User", help="Add a new user"):
                hashed = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt())
                conn = sqlite3.connect('orders.db')
                c = conn.cursor()
                try:
                    c.execute("INSERT INTO users (id, username, password, is_admin) VALUES (?, ?, ?, ?)",
                             (str(uuid.uuid4()), new_username, hashed, False))
                    conn.commit()
                    st.success("User added successfully!")
                except sqlite3.IntegrityError:
                    st.error("Username already exists")
                conn.close()
        st.markdown('</div>', unsafe_allow_html=True)
        
        st.markdown('<div class="bg-white p-8 rounded-xl shadow-md mb-8 card">', unsafe_allow_html=True)
        st.markdown('<h2 class="text-xl font-semibold text-gray-700 mb-4">Manage Timeline Stages</h2>', unsafe_allow_html=True)
        with st.form("add_stage_form"):
            new_stage = st.text_input("New Stage Name", placeholder="Enter new stage name")
            if st.form_submit_button("Add Stage", help="Add a new timeline stage"):
                stages = get_stages()
                position = max([s[2] for s in stages]) + 1 if stages else 1
                conn = sqlite3.connect('orders.db')
                c = conn.cursor()
                c.execute("INSERT INTO stages (id, name, position) VALUES (?, ?, ?)", (str(uuid.uuid4()), new_stage, position))
                conn.commit()
                conn.close()
                st.success("Stage added!")
        st.markdown('</div>', unsafe_allow_html=True)
        
        st.markdown('<div class="bg-white p-8 rounded-xl shadow-md mb-8 card">', unsafe_allow_html=True)
        st.markdown('<h2 class="text-xl font-semibold text-gray-700 mb-4">Manage Service List</h2>', unsafe_allow_html=True)
        with st.form("add_service_list_form"):
            new_service = st.text_input("New Service Name", placeholder="Enter new service name")
            if st.form_submit_button("Add Service", help="Add a new service to the list"):
                conn = sqlite3.connect('orders.db')
                c = conn.cursor()
                c.execute("INSERT INTO services_list (id, name) VALUES (?, ?)", (str(uuid.uuid4()), new_service))
                conn.commit()
                conn.close()
                st.success("Service added to list!")
        st.markdown('</div>', unsafe_allow_html=True)
        
        st.markdown('<div class="bg-white p-8 rounded-xl shadow-md mb-8 card">', unsafe_allow_html=True)
        st.markdown('<h2 class="text-xl font-semibold text-gray-700 mb-4">Rename Stage</h2>', unsafe_allow_html=True)
        with st.form("rename_stage_form"):
            stages = get_stages()
            stage_id = st.selectbox("Select Stage to Rename", options=[s[0] for s in stages], format_func=lambda x: [s[1] for s in stages if s[0] == x][0])
            new_name = st.text_input("New Stage Name", placeholder="Enter new stage name")
            if st.form_submit_button("Rename Stage", help="Rename the selected stage"):
                conn = sqlite3.connect('orders.db')
                c = conn.cursor()
                c.execute("UPDATE stages SET name = ? WHERE id = ?", (new_name, stage_id))
                c.execute("UPDATE services SET stage = ? WHERE stage = ?", (new_name, [s[1] for s in stages if s[0] == stage_id][0]))
                conn.commit()
                conn.close()
                st.success("Stage renamed!")
        st.markdown('</div>', unsafe_allow_html=True)
        
        st.markdown('<div class="bg-white p-8 rounded-xl shadow-md mb-8 card">', unsafe_allow_html=True)
        st.markdown('<h2 class="text-xl font-semibold text-gray-700 mb-4">Add Custom Contact Field</h2>', unsafe_allow_html=True)
        with st.form("add_custom_field_form"):
            new_field = st.text_input("New Field Name", placeholder="Enter new field name")
            if st.form_submit_button("Add Field", help="Add a new custom contact field"):
                add_custom_field(new_field)
                st.success("Custom field added!")
        st.markdown('</div>', unsafe_allow_html=True)
        
        st.markdown('<div class="bg-white p-8 rounded-xl shadow-md mb-8 card">', unsafe_allow_html=True)
        st.markdown('<h2 class="text-xl font-semibold text-gray-700 mb-4">Password Reset Requests</h2>', unsafe_allow_html=True)
        conn = sqlite3.connect('orders.db')
        c = conn.cursor()
        c.execute("SELECT pr.id, pr.user_id, u.username, pr.temp_password, pr.requested_at, pr.approved FROM password_resets pr JOIN users u ON pr.user_id = u.id WHERE pr.approved = 0")
        requests = c.fetchall()
        conn.close()
        for req in requests:
            reset_id, user_id, username, temp_password, requested_at, approved = req
            st.markdown(f'<p class="text-gray-600">User: {username}, Requested at: {requested_at}, Temp Password: {temp_password}</p>', unsafe_allow_html=True)
            if st.button(f"Approve Reset for {username}", key=f"approve_{reset_id}", help="Approve password reset"):
                approve_password_reset(reset_id, user_id)
                st.success(f"Password reset approved for {username}!")
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
        
        st.markdown('<div class="bg-white p-8 rounded-xl shadow-md card">', unsafe_allow_html=True)
        st.markdown('<h2 class="text-xl font-semibold text-gray-700 mb-4">View Archived Orders</h2>', unsafe_allow_html=True)
        archived_orders = get_user_orders(user_id, is_admin, include_archived=True)
        archived_orders = [o for o in archived_orders if o[7]]  # archived = True
        for order in archived_orders:
            order_id, _, business_name, _, _, _, created_at, _ = order
            st.markdown(f'<p class="text-gray-600">Order: {business_name} (Created: {created_at})</p>', unsafe_allow_html=True)
            if st.button(f"Restore Order: {business_name}", key=f"restore_{order_id}", help="Restore this order"):
                restore_order(order_id, user_id)
                st.success(f"Order {business_name} restored!")
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    # Admin Dashboard Page
    elif page == 'admin-dashboard' and is_admin and username == 'chadillac':
        st.markdown('<h1 class="text-3xl font-bold text-gray-800 mb-6">Admin Dashboard</h1>', unsafe_allow_html=True)
        st.markdown(f'<p class="text-gray-600 mb-6">Logged in as: {username}</p>', unsafe_allow_html=True)

        # User Selection
        st.markdown('<div class="bg-white p-8 rounded-xl shadow-md mb-8 card">', unsafe_allow_html=True)
        st.markdown('<h2 class="text-xl font-semibold text-gray-700 mb-4">View User Orders</h2>', unsafe_allow_html=True)
        users = get_all_users()
        user_options = [(u[0], u[1]) for u in users]
        user_dict = {u[1]: u[0] for u in users}
        user_dict['See All'] = 'all'
        selected_user = st.selectbox("Select User", options=['See All'] + [u[1] for u in user_options], key="user_select")
        st.markdown('</div>', unsafe_allow_html=True)

        # Order Status Table
        st.markdown('<div class="bg-white p-8 rounded-xl shadow-md card overflow-x-auto">', unsafe_allow_html=True)
        st.markdown('<h2 class="text-xl font-semibold text-gray-700 mb-4">Order Status</h2>', unsafe_allow_html=True)
        st.markdown('<table class="min-w-full divide-y divide-gray-200">', unsafe_allow_html=True)
        st.markdown('<thead class="bg-gray-50"><tr><th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">User</th><th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Order</th><th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Services</th><th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Progress</th></tr></thead>', unsafe_allow_html=True)
        st.markdown('<tbody class="bg-white divide-y divide-gray-200">', unsafe_allow_html=True)
        
        if selected_user == 'See All':
            orders = get_all_active_orders()
            for order in orders:
                order_id, user_id, business_name, _, _, _, _, _, username = order
                services = get_order_services(order_id)
                service_list = ", ".join([s[1] for s in services]) or "No services"
                progress = get_order_progress(order_id)
                st.markdown(f'<tr><td class="px-6 py-4 whitespace-nowrap"><div class="text-sm text-gray-500">{username}</div></td>', unsafe_allow_html=True)
                st.markdown(f'<td class="px-6 py-4 whitespace-nowrap"><div class="text-sm font-medium text-gray-900">{business_name}</div></td>', unsafe_allow_html=True)
                st.markdown(f'<td class="px-6 py-4 whitespace-nowrap"><div class="text-sm text-gray-500">{service_list}</div></td>', unsafe_allow_html=True)
                st.markdown(f'<td class="px-6 py-4 whitespace-nowrap"><div class="w-64 bg-gray-200 rounded-full h-2.5"><div class="bg-gradient-to-r from-blue-500 to-blue-600 h-2.5 rounded-full" style="width: {progress}%"></div></div><span class="ml-2 text-sm text-gray-500">{progress}%</span></td></tr>', unsafe_allow_html=True)
        else:
            user_id = user_dict[selected_user]
            orders = get_orders_for_user(user_id)
            for order in orders:
                order_id, _, business_name, _, _, _, _, _ = order
                services = get_order_services(order_id)
                service_list = ", ".join([s[1] for s in services]) or "No services"
                progress = get_order_progress(order_id)
                st.markdown(f'<tr><td class="px-6 py-4 whitespace-nowrap"><div class="text-sm text-gray-500">{selected_user}</div></td>', unsafe_allow_html=True)
                st.markdown(f'<td class="px-6 py-4 whitespace-nowrap"><div class="text-sm font-medium text-gray-900">{business_name}</div></td>', unsafe_allow_html=True)
                st.markdown(f'<td class="px-6 py-4 whitespace-nowrap"><div class="text-sm text-gray-500">{service_list}</div></td>', unsafe_allow_html=True)
                st.markdown(f'<td class="px-6 py-4 whitespace-nowrap"><div class="w-64 bg-gray-200 rounded-full h-2.5"><div class="bg-gradient-to-r from-blue-500 to-blue-600 h-2.5 rounded-full" style="width: {progress}%"></div></div><span class="ml-2 text-sm text-gray-500">{progress}%</span></td></tr>', unsafe_allow_html=True)
        
        st.markdown('</tbody></table></div>', unsafe_allow_html=True)

    # Close the main container
    st.markdown('</div></div>', unsafe_allow_html=True)