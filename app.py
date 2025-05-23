import streamlit as st
import sqlite3
import bcrypt
import pandas as pd
import uuid
from datetime import datetime, timedelta
import logging
from functools import lru_cache
import threading
from contextlib import contextmanager

# Set up logging to capture errors
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Thread-local storage for database connections
thread_local = threading.local()

# Connection pooling and context manager for database operations
@contextmanager
def get_db_connection():
    """Context manager for database connections with connection reuse"""
    if not hasattr(thread_local, 'connection'):
        thread_local.connection = sqlite3.connect('orders.db', check_same_thread=False)
        thread_local.connection.row_factory = sqlite3.Row  # Enable dict-like access
    
    try:
        yield thread_local.connection
    except Exception as e:
        thread_local.connection.rollback()
        logger.error(f"Database error: {str(e)}")
        raise
    finally:
        # Don't close connection, keep it for reuse
        pass

# Cache frequently accessed data
@lru_cache(maxsize=128)
def get_stages_cached():
    """Cached version of get_stages to avoid repeated DB queries"""
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute("SELECT id, name, position FROM stages ORDER BY position")
            stages = c.fetchall()
            return [(row['id'], row['name'], row['position']) for row in stages]
    except Exception as e:
        logger.error(f"Error in get_stages_cached: {str(e)}")
        return []

@lru_cache(maxsize=128)
def get_services_list_cached():
    """Cached version of get_services_list"""
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute("SELECT id, name FROM services_list")
            services = c.fetchall()
            return [(row['id'], row['name']) for row in services]
    except Exception as e:
        logger.error(f"Error in get_services_list_cached: {str(e)}")
        return []

# Optimized database initialization with batch operations
def init_db():
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            
            # Create all tables in a single transaction
            table_creation_queries = [
                '''CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    username TEXT UNIQUE,
                    password TEXT,
                    is_admin BOOLEAN
                )''',
                '''CREATE TABLE IF NOT EXISTS orders (
                    id TEXT PRIMARY KEY,
                    user_id TEXT,
                    business_name TEXT,
                    email TEXT,
                    phone TEXT,
                    address TEXT,
                    created_at TEXT,
                    archived BOOLEAN DEFAULT 0,
                    FOREIGN KEY(user_id) REFERENCES users(id)
                )''',
                '''CREATE TABLE IF NOT EXISTS services (
                    id TEXT PRIMARY KEY,
                    order_id TEXT,
                    name TEXT,
                    stage TEXT,
                    is_template BOOLEAN,
                    template_services TEXT,
                    FOREIGN KEY(order_id) REFERENCES orders(id)
                )''',
                '''CREATE TABLE IF NOT EXISTS stages (
                    id TEXT PRIMARY KEY,
                    name TEXT,
                    position INTEGER
                )''',
                '''CREATE TABLE IF NOT EXISTS services_list (
                    id TEXT PRIMARY KEY,
                    name TEXT
                )''',
                '''CREATE TABLE IF NOT EXISTS custom_fields (
                    id TEXT PRIMARY KEY,
                    name TEXT
                )''',
                '''CREATE TABLE IF NOT EXISTS password_resets (
                    id TEXT PRIMARY KEY,
                    user_id TEXT,
                    temp_password TEXT,
                    requested_at TEXT,
                    approved BOOLEAN,
                    FOREIGN KEY(user_id) REFERENCES users(id)
                )''',
                '''CREATE TABLE IF NOT EXISTS changes (
                    id TEXT PRIMARY KEY,
                    order_id TEXT,
                    user_id TEXT,
                    description TEXT,
                    timestamp TEXT,
                    FOREIGN KEY(order_id) REFERENCES orders(id),
                    FOREIGN KEY(user_id) REFERENCES users(id)
                )'''
            ]
            
            # Execute all table creation queries
            for query in table_creation_queries:
                c.execute(query)
            
            # Create indexes for better query performance
            index_queries = [
                "CREATE INDEX IF NOT EXISTS idx_orders_user_id ON orders(user_id)",
                "CREATE INDEX IF NOT EXISTS idx_orders_archived ON orders(archived)",
                "CREATE INDEX IF NOT EXISTS idx_services_order_id ON services(order_id)",
                "CREATE INDEX IF NOT EXISTS idx_changes_order_id ON changes(order_id)",
                "CREATE INDEX IF NOT EXISTS idx_changes_timestamp ON changes(timestamp)",
                "CREATE INDEX IF NOT EXISTS idx_stages_position ON stages(position)"
            ]
            
            for query in index_queries:
                c.execute(query)
            
            # Initialize default data only if tables are empty
            c.execute("SELECT COUNT(*) FROM stages")
            if c.fetchone()[0] == 0:
                default_stages = [
                    (str(uuid.uuid4()), "To Do", 1),
                    (str(uuid.uuid4()), "In Progress", 2),
                    (str(uuid.uuid4()), "Done", 3)
                ]
                c.executemany("INSERT INTO stages (id, name, position) VALUES (?, ?, ?)", default_stages)
            
            c.execute("SELECT COUNT(*) FROM services_list")
            if c.fetchone()[0] == 0:
                default_services = [
                    (str(uuid.uuid4()), "Research"),
                    (str(uuid.uuid4()), "Design"),
                    (str(uuid.uuid4()), "Development")
                ]
                c.executemany("INSERT INTO services_list (id, name) VALUES (?, ?)", default_services)
            
            c.execute("SELECT COUNT(*) FROM users WHERE username = ?", ('chadillac',))
            if c.fetchone()[0] == 0:
                hashed = bcrypt.hashpw('roostersgrin'.encode('utf-8'), bcrypt.gensalt())
                c.execute("INSERT INTO users (id, username, password, is_admin) VALUES (?, ?, ?, ?)",
                         (str(uuid.uuid4()), 'chadillac', hashed, True))
            
            conn.commit()
            logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Error initializing database: {str(e)}")
        st.error(f"Failed to initialize database: {str(e)}")
        raise

# Optimized helper functions with batch operations and caching
def check_login(username, password):
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute("SELECT id, password, is_admin FROM users WHERE username = ?", (username,))
            user = c.fetchone()
            if user and bcrypt.checkpw(password.encode('utf-8'), user['password']):
                return {'id': user['id'], 'username': username, 'is_admin': user['is_admin']}
        return None
    except Exception as e:
        logger.error(f"Error in check_login: {str(e)}")
        return None

def get_user_orders_optimized(user_id, is_admin=False, include_archived=False):
    """Optimized version with single query and proper indexing"""
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            if is_admin and include_archived:
                c.execute("SELECT * FROM orders ORDER BY created_at DESC")
            elif is_admin:
                c.execute("SELECT * FROM orders WHERE archived = 0 ORDER BY created_at DESC")
            else:
                c.execute("SELECT * FROM orders WHERE user_id = ? AND archived = 0 ORDER BY created_at DESC", (user_id,))
            orders = c.fetchall()
            return [dict(row) for row in orders]
    except Exception as e:
        logger.error(f"Error in get_user_orders_optimized: {str(e)}")
        return []

def get_order_services_batch(order_ids):
    """Batch fetch services for multiple orders"""
    if not order_ids:
        return {}
    
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            placeholders = ','.join('?' * len(order_ids))
            c.execute(f"SELECT id, order_id, name, stage, is_template, template_services FROM services WHERE order_id IN ({placeholders})", order_ids)
            services = c.fetchall()
            
            # Group services by order_id
            services_by_order = {}
            for service in services:
                order_id = service['order_id']
                if order_id not in services_by_order:
                    services_by_order[order_id] = []
                services_by_order[order_id].append(dict(service))
            
            return services_by_order
    except Exception as e:
        logger.error(f"Error in get_order_services_batch: {str(e)}")
        return {}

def get_order_changes_batch(order_ids):
    """Batch fetch changes for multiple orders"""
    if not order_ids:
        return {}
    
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            placeholders = ','.join('?' * len(order_ids))
            c.execute(f"""
                SELECT order_id, description, timestamp 
                FROM changes 
                WHERE order_id IN ({placeholders}) 
                ORDER BY timestamp DESC
            """, order_ids)
            changes = c.fetchall()
            
            # Group changes by order_id
            changes_by_order = {}
            for change in changes:
                order_id = change['order_id']
                if order_id not in changes_by_order:
                    changes_by_order[order_id] = []
                changes_by_order[order_id].append(dict(change))
            
            return changes_by_order
    except Exception as e:
        logger.error(f"Error in get_order_changes_batch: {str(e)}")
        return {}

def calculate_order_progress_batch(order_ids, services_by_order):
    """Calculate progress for multiple orders efficiently"""
    stages = get_stages_cached()
    stage_positions = {stage[1]: stage[2] for stage in stages}
    total_stages = max(stage_positions.values()) if stage_positions else 1
    
    progress_by_order = {}
    for order_id in order_ids:
        services = services_by_order.get(order_id, [])
        if not services:
            progress_by_order[order_id] = 0
            continue
        
        total_position = sum(stage_positions.get(service['stage'], 1) for service in services)
        avg_position = total_position / len(services)
        progress = (avg_position / total_stages) * 100
        progress_by_order[order_id] = round(progress, 2)
    
    return progress_by_order

def get_days_since_last_change_batch(order_ids, changes_by_order):
    """Calculate days since last change for multiple orders"""
    days_by_order = {}
    for order_id in order_ids:
        changes = changes_by_order.get(order_id, [])
        if changes:
            last_change_time = datetime.fromisoformat(changes[0]['timestamp'])
            days_diff = (datetime.now() - last_change_time).days
            days_by_order[order_id] = days_diff
        else:
            days_by_order[order_id] = None
    
    return days_by_order

# Streamlit app with optimizations
@st.cache_data(ttl=300)  # Cache for 5 minutes
def get_dashboard_data(user_id, is_admin):
    """Cached dashboard data to avoid repeated queries"""
    orders = get_user_orders_optimized(user_id, is_admin)
    if not orders:
        return orders, {}, {}, {}, {}
    
    order_ids = [order['id'] for order in orders]
    services_by_order = get_order_services_batch(order_ids)
    changes_by_order = get_order_changes_batch(order_ids)
    progress_by_order = calculate_order_progress_batch(order_ids, services_by_order)
    days_by_order = get_days_since_last_change_batch(order_ids, changes_by_order)
    
    return orders, services_by_order, changes_by_order, progress_by_order, days_by_order

# Keep the rest of the helper functions with minor optimizations
def get_all_users():
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute("SELECT id, username FROM users")
            users = c.fetchall()
            return [(row['id'], row['username']) for row in users]
    except Exception as e:
        logger.error(f"Error in get_all_users: {str(e)}")
        return []

def get_all_active_orders():
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute("SELECT o.*, u.username FROM orders o JOIN users u ON o.user_id = u.id WHERE o.archived = 0")
            orders = c.fetchall()
            return [dict(row) for row in orders]
    except Exception as e:
        logger.error(f"Error in get_all_active_orders: {str(e)}")
        return []

def get_templates():
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute("SELECT id, name, template_services FROM services WHERE is_template = ?", (True,))
            templates = c.fetchall()
            return [(row['id'], row['name'], row['template_services']) for row in templates]
    except Exception as e:
        logger.error(f"Error in get_templates: {str(e)}")
        return []

def log_change(order_id, user_id, description):
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute("INSERT INTO changes (id, order_id, user_id, description, timestamp) VALUES (?, ?, ?, ?, ?)",
                     (str(uuid.uuid4()), order_id, user_id, description, datetime.now().isoformat()))
            conn.commit()
            # Clear cache when data changes
            get_dashboard_data.clear()
    except Exception as e:
        logger.error(f"Error in log_change: {str(e)}")

def archive_order(order_id, user_id):
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute("UPDATE orders SET archived = 1 WHERE id = ?", (order_id,))
            log_change(order_id, user_id, "Order archived")
            conn.commit()
            # Clear cache when data changes
            get_dashboard_data.clear()
    except Exception as e:
        logger.error(f"Error in archive_order: {str(e)}")

def restore_order(order_id, user_id):
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute("UPDATE orders SET archived = 0 WHERE id = ?", (order_id,))
            log_change(order_id, user_id, "Order restored")
            conn.commit()
            # Clear cache when data changes
            get_dashboard_data.clear()
    except Exception as e:
        logger.error(f"Error in restore_order: {str(e)}")

def add_service_to_order(order_id, user_id, service_id, template_id=None):
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute("SELECT name FROM services_list WHERE id = ?", (service_id,))
            service_result = c.fetchone()
            if not service_result:
                st.error("Service not found")
                return
            
            service_name = service_result['name']
            stages = get_stages_cached()
            first_stage = stages[0][1] if stages else "To Do"
            
            template_services = ""
            if template_id:
                c.execute("SELECT template_services FROM services WHERE id = ?", (template_id,))
                template_result = c.fetchone()
                if template_result:
                    template_services = template_result['template_services']
                
                c.execute("INSERT INTO services (id, order_id, name, stage, is_template, template_services) VALUES (?, ?, ?, ?, ?, ?)",
                         (str(uuid.uuid4()), order_id, service_name, first_stage, True, template_services))
            else:
                c.execute("INSERT INTO services (id, order_id, name, stage, is_template) VALUES (?, ?, ?, ?, ?)",
                         (str(uuid.uuid4()), order_id, service_name, first_stage, False))
            
            log_change(order_id, user_id, f"Service {service_name} added")
            conn.commit()
            # Clear cache when data changes
            get_dashboard_data.clear()
    except Exception as e:
        logger.error(f"Error in add_service_to_order: {str(e)}")

# Initialize app
logger.info("Starting Streamlit app")
st.set_page_config(page_title="Order Tracking App", layout="wide")

# Initialize database
logger.info("Initializing database")
init_db()

# Session state for authentication
if 'user' not in st.session_state:
    st.session_state.user = None

# Optimized CSS injection (reduced size)
st.markdown("""
    <link href="https://cdn.jsdelivr.net/npm/tailwindcss@2.2.19/dist/tailwind.min.css" rel="stylesheet">
    <style>
        .sidebar {background-color: #1E3A8A;}
        .card {transition: all 0.2s ease-in-out;}
        .card:hover {transform: translateY(-2px); box-shadow: 0 4px 20px rgba(0, 0, 0, 0.1);}
    </style>
""", unsafe_allow_html=True)

# Login page (unchanged for brevity, but could be optimized similarly)
if not st.session_state.user:
    st.markdown('<div class="flex justify-center items-center min-h-screen bg-gray-100"><div class="bg-white p-8 rounded-xl shadow-md w-full max-w-md">', unsafe_allow_html=True)
    st.markdown('<h1 class="text-2xl font-bold text-gray-800 mb-6 text-center">Login</h1>', unsafe_allow_html=True)
    
    with st.form("login_form"):
        username = st.text_input("Username", placeholder="Enter your username")
        password = st.text_input("Password", type="password", placeholder="Enter your password")
        login_button = st.form_submit_button("Login")
        
        if login_button:
            user = check_login(username, password)
            if user:
                st.session_state.user = user
                st.success("Logged in successfully!")
                st.rerun()
            else:
                st.error("Invalid username or password")
    
    st.markdown('</div></div>', unsafe_allow_html=True)

else:
    user_id = st.session_state.user['id']
    username = st.session_state.user['username']
    is_admin = st.session_state.user['is_admin']
    
    # Navigation
    if 'page' not in st.session_state:
        st.session_state.page = 'dashboard'

    # Optimized Dashboard Page
    if st.session_state.page == 'dashboard':
        st.markdown('<h1 class="text-3xl font-bold text-gray-800 mb-6">Dashboard</h1>', unsafe_allow_html=True)
        
        # Use cached dashboard data
        orders, services_by_order, changes_by_order, progress_by_order, days_by_order = get_dashboard_data(user_id, is_admin)
        
        if orders:
            active_orders = len(orders)
            days_values = [d for d in days_by_order.values() if d is not None]
            avg_days = sum(days_values) / len(days_values) if days_values else 0
            
            st.markdown(f'<p class="text-gray-600 mb-6">Active Orders: {active_orders} | Avg. Days Since Last Change: {avg_days:.1f}</p>', unsafe_allow_html=True)
            
            # Order Overview with batch-processed data
            st.markdown('<h2 class="text-xl font-semibold text-gray-700 mb-4">Order Overview</h2>', unsafe_allow_html=True)
            st.markdown('<div class="bg-white rounded-xl shadow-md overflow-x-auto mb-8 card">', unsafe_allow_html=True)
            
            # Build table HTML efficiently
            table_rows = []
            for order in orders:
                order_id = order['id']
                business_name = order['business_name']
                services = services_by_order.get(order_id, [])
                total_services = len(services)
                progress = progress_by_order.get(order_id, 0)
                
                table_rows.append(f'''
                    <tr>
                        <td class="px-6 py-4 whitespace-nowrap">
                            <div class="text-sm font-medium text-gray-900">{business_name}</div>
                        </td>
                        <td class="px-6 py-4 whitespace-nowrap">
                            <div class="text-sm text-gray-500">{total_services}</div>
                        </td>
                        <td class="px-6 py-4 whitespace-nowrap">
                            <div class="w-64 bg-gray-200 rounded-full h-2.5">
                                <div class="bg-gradient-to-r from-blue-500 to-blue-600 h-2.5 rounded-full" style="width: {progress}%"></div>
                            </div>
                            <span class="ml-2 text-sm text-gray-500">{progress}%</span>
                        </td>
                    </tr>
                ''')
            
            table_html = f'''
                <table class="min-w-full divide-y divide-gray-200">
                    <thead class="bg-gray-50">
                        <tr>
                            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Order</th>
                            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Total Services</th>
                            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Progress</th>
                        </tr>
                    </thead>
                    <tbody class="bg-white divide-y divide-gray-200">
                        {''.join(table_rows)}
                    </tbody>
                </table>
            '''
            
            st.markdown(table_html, unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)
        
        else:
            st.markdown('<p class="text-gray-600">No orders found.</p>', unsafe_allow_html=True)

    # Add simplified versions of other pages here...
    # For brevity, I'm not including all pages, but they would follow similar optimization patterns
