import streamlit as st
import pandas as pd
import numpy as np
from tensorflow.keras.models import load_model
from sklearn.preprocessing import MinMaxScaler
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import hashlib
import warnings
import os
import time
import pytz # Import pytz for timezone handling

warnings.filterwarnings('ignore')

# =============================================================================
# ⚙️ KONFIGURASI APLIKASI GLOBAL (HARUS DI BAGIAN ATAS DAN HANYA SEKALI)
# =============================================================================
st.set_page_config(
    page_title="Industrial Gas Removal Monitoring System",
    page_icon="🏭",
    layout="wide",
    initial_sidebar_state="expanded" # Atur ini sesuai keinginan awal sidebar
)

# =============================================================================
# 🔧 KONFIGURASI FILE CSV DAN AUTO-UPDATE
# =============================================================================

# GANTI NAMA FILE CSV ANDA DI SINI
# Pastikan file CSV berada di folder yang sama dengan script Python ini
CSV_FILE_NAME = "data2parfull.csv"  # <-- GANTI DENGAN NAMA FILE CSV ANDA

# Path lengkap ke file CSV (otomatis mengambil dari folder yang sama)
CSV_FILE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), CSV_FILE_NAME)

# Interval update default dalam detik (3 jam = 10800 detik)
DEFAULT_UPDATE_INTERVAL = 10800  # Default 3 jam
# Catatan: Untuk debugging, Anda bisa mengubah ini ke 60 (1 menit)
# DEFAULT_UPDATE_INTERVAL = 60 

# Define the target timezone (Indonesia/Jakarta for WIB)
INDONESIA_TIMEZONE = pytz.timezone('Asia/Jakarta')

# =============================================================================
# 🔐 SECURE AUTHENTICATION SYSTEM
# =============================================================================

def hash_password(password):
    """Secure password hashing using SHA256"""
    return hashlib.sha256(password.encode()).hexdigest()

# Industrial-grade user credentials
USER_CREDENTIALS = {
    "engineer": hash_password("engineer123"),
    "supervisor": hash_password("supervisor123"),
    "admin": hash_password("admin123"),
}

USER_ROLES = {
    "engineer": {
        "name": "Plant Engineer", 
        "role": "Engineer",
        "department": "Process Engineering",
        "permissions": ["view", "analyze"]
    },
    "supervisor": {
        "name": "Operations Supervisor", 
        "role": "Supervisor",
        "department": "Operations",
        "permissions": ["view", "analyze", "export"]
    },
    "admin": {
        "name": "System Administrator", 
        "role": "Administrator",
        "department": "IT & Maintenance",
        "permissions": ["view", "analyze", "export", "configure"]
    },
}

def check_authentication():
    return st.session_state.get('authenticated', False)

def authenticate_user(username, password):
    if username in USER_CREDENTIALS:
        return USER_CREDENTIALS[username] == hash_password(password)
    return False

# =============================================================================
# 🔄 AUTO-UPDATE FUNCTIONS
# =============================================================================

def get_current_localized_time():
    """Get the current time localized to the Indonesia timezone."""
    return datetime.now(INDONESIA_TIMEZONE)

def init_session_state():
    """Initialize session state variables for auto-update functionality"""
    if 'last_update_time' not in st.session_state:
        st.session_state.last_update_time = get_current_localized_time()
    
    if 'update_interval' not in st.session_state:
        st.session_state.update_interval = DEFAULT_UPDATE_INTERVAL
    
    if 'auto_update_enabled' not in st.session_state:
        st.session_state.auto_update_enabled = True
    
    if 'csv_data' not in st.session_state:
        st.session_state.csv_data = None
    
    if 'last_file_modified' not in st.session_state:
        st.session_state.last_file_modified = None
    
    if 'selected_interval_label' not in st.session_state:
        st.session_state.selected_interval_label = '3 hours'

# Menggunakan st.cache_data untuk caching data
# ttl (Time To Live) diatur ke interval update, jadi data akan di-cache selama itu
@st.cache_data(ttl=DEFAULT_UPDATE_INTERVAL)
def load_csv_automatically(file_path):
    """
    Fungsi untuk memuat file CSV secara otomatis.
    Menggunakan st.cache_data agar data di-cache selama interval tertentu.
    Parameter `file_path` ditambahkan agar `st.cache_data` dapat mendeteksi perubahan jika path berubah (walaupun tidak akan di sini).
    """
    st.sidebar.info(f"⚙️ Loading data from {os.path.basename(file_path)}...")
    
    try:
        if not os.path.exists(file_path):
            st.sidebar.error(f"❌ File tidak ditemukan: {os.path.basename(file_path)}")
            st.sidebar.info("Pastikan file CSV berada di folder yang sama dengan script ini")
            return None
        
        delimiters = [',', ';', '\t']
        df = None
        
        for delimiter in delimiters:
            try:
                df = pd.read_csv(file_path, sep=delimiter)
                if len(df.columns) > 1: # Cek apakah sudah terbaca dengan benar (lebih dari 1 kolom)
                    break
            except Exception:
                continue
        
        if df is None:
            st.sidebar.error(f"❌ Gagal membaca file: {os.path.basename(file_path)}. Coba format delimiter lain.")
            return None
        
        st.sidebar.success(f"✅ Data '{os.path.basename(file_path)}' dimuat!")
        return df
        
    except Exception as e:
        st.sidebar.error(f"❌ Error loading CSV: {str(e)}")
        return None

def check_and_update():
    """
    Cek apakah sudah waktunya update data.
    Update otomatis jika interval waktu sudah tercapai dan auto-update aktif.
    """
    current_time = get_current_localized_time()
    time_diff = (current_time - st.session_state.last_update_time).total_seconds()
    
    if time_diff >= st.session_state.update_interval and st.session_state.auto_update_enabled:
        st.session_state.last_update_time = current_time
        # Memaksa cache di-invalidate agar data dimuat ulang dari sumber
        load_csv_automatically.clear() 
        st.rerun()

def format_time_remaining():
    """Format waktu yang tersisa sampai update berikutnya"""
    current_time = get_current_localized_time()
    time_diff = (current_time - st.session_state.last_update_time).total_seconds()
    time_remaining = st.session_state.update_interval - time_diff
    
    if time_remaining <= 0:
        return "Update pending..."
    
    hours = int(time_remaining // 3600)
    minutes = int((time_remaining % 3600) // 60)
    seconds = int(time_remaining % 60)
    
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

def login_page():
    # st.set_page_config() dihapus dari sini karena sudah ada di paling atas
    
    # Professional login styling
    st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
        
        .main {
            background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
            font-family: 'Inter', sans-serif;
        }
        
        .login-container {
            max-width: 450px;
            margin: 5% auto;
            padding: 40px;
            background: rgba(255, 255, 255, 0.95);
            border-radius: 20px;
            box-shadow: 0 20px 40px rgba(0, 0, 0, 0.1);
            backdrop-filter: blur(10px);
        }
        
        .company-header {
            text-align: center;
            margin-bottom: 30px;
        }
        
        .company-logo {
            font-size: 3rem;
            color: #1e3c72;
            margin-bottom: 10px;
        }
        
        .company-title {
            color: #1e3c72;
            font-size: 1.8rem;
            font-weight: 700;
            margin-bottom: 5px;
        }
        
        .system-subtitle {
            color: #666;
            font-size: 1rem;
            font-weight: 400;
        }
        
        .login-form {
            margin-top: 30px;
        }
        
        .stTextInput > div > div > input {
            border: 2px solid #e1e5e9;
            border-radius: 10px;
            padding: 12px 16px;
            font-size: 1rem;
            transition: all 0.3s ease;
        }
        
        .stTextInput > div > div > input:focus {
            border-color: #1e3c72;
            box-shadow: 0 0 0 3px rgba(30, 60, 114, 0.1);
        }
        
        .stButton > button {
            width: 100%;
            background: linear-gradient(135deg, #1e3c72, #2a5298);
            border: none;
            border-radius: 10px;
            color: white;
            font-weight: 600;
            font-size: 1rem;
            padding: 12px;
            transition: all 0.3s ease;
        }
        
        .stButton > button:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 20px rgba(30, 60, 114, 0.3);
        }
        
        .security-footer {
            text-align: center;
            margin-top: 30px;
            padding-top: 20px;
            border-top: 1px solid #e1e5e9;
            color: #666;
            font-size: 0.9rem;
        }
        
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)
    
    # Login container
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown("""
        <div class="login-container">
            <div class="company-header">
                <div class="company-logo">🏭</div>
                <h1 class="company-title">Industrial Monitoring System</h1>
                <p class="system-subtitle">Gas Removal Predictive Maintenance</p>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        with st.form("secure_login"):
            st.markdown("### 🔐 Secure Access")
            st.markdown("Please authenticate to access the industrial monitoring system.")
            
            username = st.text_input("👤 Username", placeholder="Enter your username")
            password = st.text_input("🔑 Password", type="password", placeholder="Enter your password")
            
            login_button = st.form_submit_button("🚀 Access System")
            
            if login_button:
                if username and password:
                    if authenticate_user(username, password):
                        st.session_state['authenticated'] = True
                        st.session_state['username'] = username
                        st.session_state['user_info'] = USER_ROLES.get(username, {})
                        st.success("✅ Authentication successful! Loading system...")
                        time.sleep(1) # Beri sedikit waktu untuk pesan sukses terlihat
                        st.rerun() # Memuat ulang aplikasi untuk masuk ke dashboard
                    else:
                        st.error("❌ Invalid credentials. Access denied.")
                else:
                    st.warning("⚠️ Please provide both username and password.")
        
        st.markdown("""
        <div class="security-footer">
            <p>🔒 Secure Industrial System Access</p>
            <p><strong>Demo Credentials:</strong><br>
            engineer/engineer123 | supervisor/supervisor123 | admin/admin123</p>
        </div>
        """, unsafe_allow_html=True)

def logout():
    for key in ['authenticated', 'username', 'user_info', 'csv_data', 'last_file_modified', 'last_update_time']:
        if key in st.session_state:
            del st.session_state[key]
    # Hapus cache st.cache_data agar data dimuat ulang saat login berikutnya
    load_csv_automatically.clear() 
    st.rerun()

def show_user_panel():
    """Professional user information panel with auto-update controls"""
    if 'user_info' in st.session_state:
        user_info = st.session_state['user_info']
        st.sidebar.markdown("### 👤 User Profile")
        
        # User card
        st.sidebar.markdown(f"""
        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                    padding: 15px; border-radius: 10px; margin-bottom: 20px;">
            <div style="color: white; font-weight: 600; font-size: 1.1rem;">
                {user_info.get('name', 'User')}
            </div>
            <div style="color: rgba(255,255,255,0.8); font-size: 0.9rem;">
                {user_info.get('role', 'User')} • {user_info.get('department', 'General')}
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Permissions
        permissions = user_info.get('permissions', [])
        st.sidebar.markdown("**Access Level:**")
        for perm in permissions:
            st.sidebar.markdown(f"✅ {perm.title()}")
        
        st.sidebar.markdown("---")
        
        # Auto-update controls
        st.sidebar.markdown("### 🔄 Auto-Update Settings")
        
        # Toggle auto-update
        st.session_state.auto_update_enabled = st.sidebar.checkbox(
            "Enable Auto-Update",
            value=st.session_state.auto_update_enabled,
            help="Automatically refresh data at specified intervals"
        )
        
        # Update interval selection
        update_options = {
            "1 minute": 60,
            "5 minutes": 300,
            "15 minutes": 900,
            "30 minutes": 1800,
            "1 hour": 3600,
            "3 hours": 10800,
            "6 hours": 21600,
            "12 hours": 43200,
            "24 hours": 86400
        }
        
        # Get current interval value and find corresponding label
        current_interval_value = st.session_state.get('update_interval', DEFAULT_UPDATE_INTERVAL)
        
        # Ensure default_index is valid
        default_index = 0
        for idx, (label, value) in enumerate(update_options.items()):
            if value == current_interval_value:
                default_index = idx
                break
        
        selected_interval = st.sidebar.selectbox(
            "Update Interval",
            options=list(update_options.keys()),
            index=default_index,
            key="update_interval_selector", # Tambahkan key unik
            help="How often to refresh the data"
        )
        
        # Pastikan session state update_interval diperbarui hanya jika ada perubahan
        if update_options[selected_interval] != st.session_state.update_interval:
            st.session_state.update_interval = update_options[selected_interval]
            # Clear cache st.cache_data jika interval berubah agar TTL baru diterapkan
            load_csv_automatically.clear() 
            st.rerun() # Rerun untuk menerapkan interval baru

        st.session_state.selected_interval_label = selected_interval
        
        # Show current status
        st.sidebar.markdown("**Auto-Update Status:**")
        if st.session_state.auto_update_enabled:
            st.sidebar.info(f"🕐 Next update in: {format_time_remaining()}")
        else:
            st.sidebar.warning("⏸️ Auto-update disabled")
        
        # Manual refresh button
        if st.sidebar.button("🔄 Refresh Now", type="secondary"):
            # Clear cache st.cache_data saat refresh manual
            load_csv_automatically.clear()
            st.session_state.last_update_time = get_current_localized_time() # Reset waktu terakhir update
            st.rerun() # Memuat ulang aplikasi
        
        # Show last update time
        st.sidebar.markdown(f"**Last Data Updated:** {st.session_state.last_update_time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        st.sidebar.markdown("---")
        
        # Current CSV file info
        st.sidebar.markdown("### 📄 Data Source")
        st.sidebar.info(f"**CSV File:** {CSV_FILE_NAME}")
        
        if os.path.exists(CSV_FILE_PATH):
            file_size = os.path.getsize(CSV_FILE_PATH) / 1024  # KB
            # Convert file modified time to localized time
            file_modified_utc = datetime.fromtimestamp(os.path.getmtime(CSV_FILE_PATH), pytz.utc)
            file_modified_local = file_modified_utc.astimezone(INDONESIA_TIMEZONE)
            st.sidebar.markdown(f"**Size:** {file_size:.2f} KB")
            st.sidebar.markdown(f"**Modified:** {file_modified_local.strftime('%Y-%m-%d %H:%M:%S %Z%z')}") # Add timezone info
        else:
            st.sidebar.error("File not found!")
        
        st.sidebar.markdown("---")
        
        if st.sidebar.button("🚪 Secure Logout", type="primary"):
            logout()

# =============================================================================
# 📊 INDUSTRIAL DASHBOARD MAIN SYSTEM
# =============================================================================

def main_dashboard():
    """Professional Industrial Dashboard with Auto-Update"""
    
    # Initialize session state (Pastikan ini dipanggil setiap kali main_dashboard dijalankan)
    init_session_state()
    
    # Check for auto-update (akan memicu st.rerun jika waktunya update)
    check_and_update()
    
    # st.set_page_config() dihapus dari sini karena sudah ada di paling atas
    
    # Professional industrial styling (dengan variabel CSS untuk tema gelap/terang)
    st.markdown(f"""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
        
        :root {{
            --main-header-start: #1e3c72; /* Dark blue for light theme */
            --main-header-end: #2a5298;   /* Lighter blue for light theme */
            
            --alert-critical-start: #ff7e7e; /* Light red for light theme */
            --alert-critical-end: #dc3545; /* Darker red for light theme */
            
            --alert-warning-start: #ffea99; /* Light yellow for light theme */
            --alert-warning-end: #ffc107;   /* Darker yellow for light theme */
            
            --alert-normal-start: #c3e6cb; /* Light green for light theme */
            --alert-normal-end: #28a745;   /* Darker green for light theme */
        }}

        [data-baseweb="theme-provider"][theme-mode="dark"] {{
            --main-header-start: #0f1c3a; /* Even darker blue for dark theme */
            --main-header-end: #1a2a4d;   /* Darker blue for dark theme */

            --alert-critical-start: #8b0000; /* Darker red for dark theme */
            --alert-critical-end: #a00000;   /* Even darker red for dark theme */

            --alert-warning-start: #8b6b00; /* Darker yellow for dark theme */
            --alert-warning-end: #a07a00;   /* Even darker yellow for dark theme */

            --alert-normal-start: #004d00; /* Darker green for dark theme */
            --alert-normal-end: #006b00;   /* Even darker green for dark theme */
        }}

        .main {{
            background-color: var(--background-color); /* Streamlit's default background */
            font-family: 'Inter', sans-serif;
        }}
        
        .main-header {{
            background: linear-gradient(90deg, var(--main-header-start) 0%, var(--main-header-end) 100%);
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 30px;
            color: white;
            text-align: center;
        }}
        
        .kpi-container {{
            background: var(--secondary-background-color); /* Streamlit's default secondary background */
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            margin-bottom: 20px;
            border-left: 4px solid var(--main-header-start); /* Use one of the header colors */
        }}
        
        .alert-critical {{
            background: linear-gradient(90deg, var(--alert-critical-start) 0%, var(--alert-critical-end) 100%);
            border-left: 4px solid var(--alert-critical-end);
            padding: 15px;
            border-radius: 8px;
            margin: 10px 0;
            color: white; /* Text color for dark alert */
        }}
        
        .alert-warning {{
            background: linear-gradient(90deg, var(--alert-warning-start) 0%, var(--alert-warning-end) 100%);
            border-left: 4px solid var(--alert-warning-end);
            padding: 15px;
            border-radius: 8px;
            margin: 10px 0;
            color: #333; /* Dark text for light alert */
        }}
        
        .alert-normal {{
            background: linear-gradient(90deg, var(--alert-normal-start) 0%, var(--alert-normal-end) 100%);
            border-left: 4px solid var(--alert-normal-end);
            padding: 15px;
            border-radius: 8px;
            margin: 10px 0;
            color: white; /* Text color for dark alert */
        }}
        
        .metric-card {{
            background: var(--secondary-background-color);
            padding: 15px;
            border-radius: 8px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
            text-align: center;
        }}
        
        .status-operational {{
            color: var(--alert-normal-end);
            font-weight: 600;
        }}
        
        .status-warning {{
            color: var(--alert-warning-end);
            font-weight: 600;
        }}
        
        .status-critical {{
            color: var(--alert-critical-end);
            font-weight: 600;
        }}
        
        .stPlotlyChart {{
            background: var(--secondary-background-color);
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            margin-bottom: 20px;
        }}
    </style>
    """, unsafe_allow_html=True)
    
    # Main header
    st.markdown("""
    <div class="main-header">
        <h1 style="margin: 0; font-size: 2.2rem;">🏭 Industrial Gas Removal Monitoring System</h1>
        <p style="margin: 10px 0 0 0; font-size: 1.1rem; opacity: 0.9;">
            Predictive Maintenance & Real-time Process Monitoring
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    # User panel with auto-update controls
    show_user_panel()
    
    # Sidebar configuration
    st.sidebar.markdown("## ⚙️ System Configuration")
    
    # Model loading
    MODEL_PATH = "best_lstm_model.h5"
    try:
        model = load_model(MODEL_PATH, compile=False)
        st.sidebar.success("✅ LSTM Model Loaded")
    except Exception as e:
        st.sidebar.error(f"❌ Model Loading Failed: {str(e)}")
        st.error("Critical System Error: Cannot load predictive model. Please contact system administrator.")
        st.stop()
    
    # System parameters
    st.sidebar.markdown("### 🎛️ System Parameters")
    
    col1, col2 = st.sidebar.columns(2)
    with col1:
        # Menentukan nilai default yang valid untuk start_date jika tidak ada data
        default_start_date = get_current_localized_time().date() - timedelta(days=7)
        start_date = st.date_input(
            "Start Date", 
            value=default_start_date,
            help="Data collection start date"
        )
    
    with col2:
        data_frequency = st.selectbox(
            "Data Frequency",
            options=["Hourly", "Daily", "Weekly", "Monthly"],
            index=0,
            help="Data sampling frequency"
        )
    
    threshold = st.sidebar.slider(
        "Critical Threshold", 
        min_value=0.05, 
        max_value=0.30, 
        value=0.14, 
        step=0.01,
        help="Critical pressure threshold for maintenance alerts"
    )
    
    sequence_length = st.sidebar.slider(
        "Prediction Sequence Length", 
        min_value=20, 
        max_value=120, 
        value=80, 
        step=10,
        help="Number of historical points used for prediction"
    )
    
    show_detailed_table = st.sidebar.checkbox("Show Detailed Data Table", value=False)
    
    # Load CSV using the cached function
    df = load_csv_automatically(CSV_FILE_PATH)
    
    if df is not None:
        # Data processing
        with st.spinner("🔄 Processing sensor data..."):
            # Identify columns
            timestamp_cols = [c for c in df.columns if any(keyword in c.lower() 
                             for keyword in ['time', 'date', 'timestamp', 'waktu', 'tanggal'])]
            
            pressure_cols = [c for c in df.columns if any(keyword in c.lower() 
                            for keyword in ['tekanan', 'pressure', 'kondensor', 'condenser'])]
            
            if not pressure_cols:
                st.error("❌ Pressure column not found. Please ensure your data contains pressure measurements.")
                st.stop()
            
            pressure_col = pressure_cols[0]
            
            # Process timestamps
            if timestamp_cols:
                timestamp_col = timestamp_cols[0]
                date_formats = [
                    '%d/%m/%Y %H:%M', '%d/%m/%Y %H:%M:%S',
                    '%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M',
                    '%d-%m-%Y %H:%M', '%m/%d/%Y %H:%M',
                    '%d/%m/%Y', '%Y-%m-%d' # Tambahkan format tanggal saja jika ada
                ]
                
                parsed_dates = None
                for date_format in date_formats:
                    try:
                        # Attempt to parse as naive datetime first
                        temp_dates = pd.to_datetime(df[timestamp_col], format=date_format)
                        if not temp_dates.isna().all():
                            # Localize to Indonesia timezone if successfully parsed
                            parsed_dates = temp_dates.dt.tz_localize(INDONESIA_TIMEZONE, errors='coerce')
                            break
                    except Exception:
                        continue
                
                if parsed_dates is None or parsed_dates.isna().all():
                    try:
                        # Fallback if parsing with explicit format fails, try inferring
                        temp_dates = pd.to_datetime(df[timestamp_col], errors='coerce')
                        if temp_dates.isna().all():
                            raise ValueError("All dates failed to parse")
                        # Localize inferred dates
                        parsed_dates = temp_dates.dt.tz_localize(INDONESIA_TIMEZONE, errors='coerce')
                    except Exception:
                        st.sidebar.warning("⚠️ Could not parse timestamp column. Generating timestamps and localizing.")
                        # Asumsi interval data per jam jika tidak ada timestamp, dan lokal ke Asia/Jakarta
                        parsed_dates = pd.date_range(start=get_current_localized_time() - timedelta(hours=len(df)-1), periods=len(df), freq='H', tz=INDONESIA_TIMEZONE)
                
                df['timestamp'] = parsed_dates
            else:
                df['timestamp'] = pd.date_range(start=get_current_localized_time() - timedelta(hours=len(df)-1), periods=len(df), freq='H', tz=INDONESIA_TIMEZONE)
                st.sidebar.warning("⚠️ No timestamp column found. Using generated localized timestamps.")
            
           # Clean and prepare data
            data = df[[pressure_col]].copy()
            data = data.apply(lambda x: pd.to_numeric(x.astype(str).str.replace(',', '.'), errors='coerce'))
            data = data.dropna()
            
            # Remove negative values
            if (data < 0).any().any():
                st.sidebar.warning("⚠️ Negative values detected and clipped to zero.")
                data = data.clip(lower=0)
            
            ground_truth_all = data.values.flatten()
            timestamps_all = df['timestamp'].iloc[:len(ground_truth_all)].tolist()
            
            # Scaling - Pindahkan ini ke atas, sebelum digunakan
            scaler = MinMaxScaler(feature_range=(0, 1))
            scaled_data_all = scaler.fit_transform(data)
            
            # === START: Perubahan untuk pemisahan data training/testing dan evaluasi ===
            # Split data into training and testing sets (e.g., 80% train, 20% test)
            train_size = int(len(scaled_data_all) * 0.8) # scaled_data_all sudah terdefinisi di sini
            
            train_data = scaled_data_all[:train_size]
            test_data = scaled_data_all[train_size:] # Data yang belum pernah dilihat model untuk evaluasi
            
            # Create sequences for training and testing
            def create_sequences(data, seq_length):
                sequences = []
                targets = []
                for i in range(len(data) - seq_length): # -seq_length karena kita memprediksi 1 langkah ke depan dari sequence_length
                    sequences.append(data[i:i+seq_length])
                    targets.append(data[i+seq_length]) # Target adalah nilai setelah sequence
                return np.array(sequences), np.array(targets)

            X_train, y_train = create_sequences(train_data, sequence_length)
            X_test, y_test = create_sequences(test_data, sequence_length) # Gunakan data tes

            # Lakukan prediksi pada data tes
            if len(X_test) > 0:
                predictions_on_test = model.predict(X_test)
                predictions_on_test_inv = scaler.inverse_transform(predictions_on_test).flatten()
                actual_test_inv = scaler.inverse_transform(y_test).flatten()
                
                # Timestamps untuk data tes yang diprediksi
                # Ini adalah timestamps untuk y_test
                test_timestamps = timestamps_all[train_size + sequence_length:]
                
                # Pastikan panjangnya sama
                if len(actual_test_inv) != len(predictions_on_test_inv):
                    min_len_test = min(len(actual_test_inv), len(predictions_on_test_inv))
                    actual_test_inv = actual_test_inv[:min_len_test]
                    predictions_on_test_inv = predictions_on_test_inv[:min_len_test]
                    test_timestamps = test_timestamps[:min_len_test]

                # Calculate metrics on the TEST SET
                mse = mean_squared_error(actual_test_inv, predictions_on_test_inv)
                mae = mean_absolute_error(actual_test_inv, predictions_on_test_inv)
                r2 = r2_score(actual_test_inv, predictions_on_test_inv)
                
                # Akurasi (sesuai definisi Anda: dalam +/- 0.01 dari nilai aktual)
                accuracy_tolerance = 0.01
                accuracy = np.mean(np.abs(actual_test_inv - predictions_on_test_inv) <= accuracy_tolerance) * 100
                
            else:
                mse, mae, r2, accuracy = 0, 0, 0, 0
                st.warning("Insufficient data for testing. Metrics set to 0. Please ensure enough data for training and testing after splitting.")
            
            # Untuk visualisasi historis, gunakan semua data
            ground_truth_for_chart = ground_truth_all
            timestamps_for_chart = timestamps_all
            
            # Untuk plotting prediksi pada data historis, ambil prediksi terakhir dari training/testing
            # atau jika tidak ada split, gunakan 'predictions_on_historical_inv' yang lama
            # Untuk tampilan yang benar, kita harus memplot aktual dan prediksinya
            # Saya akan mempertahankan 'predictions_on_historical_inv' Anda yang lama untuk visualisasi,
            # tetapi akurasi dihitung dari data test.
            
            # Jika Anda ingin menunjukkan prediksi model pada seluruh data historis untuk visualisasi,
            # Anda perlu membuat X_all_viz dan melakukan prediksi pada itu.
            # Ubah pemanggilan create_sequences agar sesuai dengan definisi baru (dengan target)
            X_all_viz_data, y_all_viz_data = create_sequences(scaled_data_all, sequence_length)
            
            if len(X_all_viz_data) > 0: # Menggunakan X_all_viz_data
                predictions_on_all_viz = model.predict(X_all_viz_data) # Menggunakan X_all_viz_data
                predictions_on_all_viz_inv = scaler.inverse_transform(predictions_on_all_viz).flatten()
                # Timestamps untuk prediksi pada semua data (dimulai dari sequence_length)
                timestamps_for_all_predictions_viz = timestamps_all[sequence_length:]
                actual_for_all_predictions_viz = scaler.inverse_transform(y_all_viz_data).flatten() # Menggunakan y_all_viz_data
            else:
                predictions_on_all_viz_inv = []
                timestamps_for_all_predictions_viz = []
                actual_for_all_predictions_viz = []

            # === END: Perubahan untuk pemisahan data training/testing dan evaluasi ===
            
            # =============================================================================
            # 🔮 PREDIKSI 1 BULAN KE DEPAN
            # =============================================================================
            
            def predict_future(model, last_sequence, scaler, sequence_length, future_steps, freq='H', timezone=None):
                """
                Memprediksi nilai masa depan menggunakan model LSTM.
                `last_sequence`: Sequence terakhir dari data historis yang diskalakan.
                `future_steps`: Jumlah langkah ke depan yang akan diprediksi (misal: 30 hari * 24 jam = 720 langkah untuk bulanan).
                `freq`: Frekuensi data (misal: 'H' untuk jam, 'D' untuk hari).
                `timezone`: Timezone untuk timestamp yang akan dibuat.
                """
                predicted_values = []
                current_sequence = last_sequence.copy()
                
                for _ in range(future_steps):
                    # Reshape untuk input model: (1, seq_length, 1)
                    input_seq = current_sequence.reshape(1, sequence_length, 1)
                    
                    # Prediksi satu langkah ke depan
                    next_pred_scaled = model.predict(input_seq, verbose=0)[0]
                    predicted_values.append(next_pred_scaled[0]) # Ambil nilai prediksi (karena output juga 1)
                    
                    # Geser sequence: hapus elemen pertama, tambahkan prediksi baru
                    current_sequence = np.append(current_sequence[1:], next_pred_scaled[0])
                
                # Inverse transform untuk mendapatkan nilai sebenarnya
                predicted_values_inv = scaler.inverse_transform(np.array(predicted_values).reshape(-1, 1)).flatten()
                return predicted_values_inv

            # Tentukan berapa banyak langkah ke depan (1 bulan)
            # Asumsi data hourly: 30 hari * 24 jam = 720 langkah
            future_steps_1_month = 30 * 24 
            
            # Dapatkan sequence terakhir dari data historis yang diskalakan
            last_sequence = scaled_data_all[-sequence_length:]
            
            # Prediksi masa depan
            future_predictions_inv = predict_future(model, last_sequence, scaler, sequence_length, future_steps_1_month, timezone=INDONESIA_TIMEZONE)
            
            # Buat timestamps untuk prediksi masa depan, pastikan berzona waktu
            last_timestamp = timestamps_all[-1]
            future_timestamps = pd.date_range(start=last_timestamp + timedelta(hours=1), 
                                              periods=future_steps_1_month, freq='H', tz=INDONESIA_TIMEZONE).tolist()
            
            # =============================================================================
            # 🚨 SYSTEM STATUS & PREDICTIVE ALERTING
            # =============================================================================

            current_pressure = ground_truth_all[-1] if len(ground_truth_all) > 0 else 0
            
            # Gunakan prediksi terakhir dari data historis sebagai 'predicted_pressure' saat ini
            # Prediksi ini dari test set
            predicted_pressure_now = predictions_on_test_inv[-1] if len(predictions_on_test_inv) > 0 else 0
            
            system_status = "OPERATIONAL"
            status_color = "status-operational"
            alert_class = "alert-normal"
            
            predicted_breach_time = None

            # Cek apakah prediksi masa depan akan menyentuh threshold
            for i, val in enumerate(future_predictions_inv):
                if val >= threshold:
                    predicted_breach_time = future_timestamps[i]
                    break
            
            if current_pressure > threshold or predicted_pressure_now > threshold:
                system_status = "CRITICAL"
                status_color = "status-critical"
                alert_class = "alert-critical"
            elif current_pressure > threshold * 0.8 or predicted_pressure_now > threshold * 0.8 or predicted_breach_time:
                system_status = "WARNING"
                status_color = "status-warning"
                alert_class = "alert-warning"

            # =============================================================================
            # 📊 MAIN DASHBOARD DISPLAY
            # =============================================================================
            
            # System status alert
            if system_status == "CRITICAL":
                st.markdown(f"""
                <div class="{alert_class}">
                    <h3>🚨 CRITICAL ALERT</h3>
                    <p><strong>Immediate maintenance required!</strong><br>
                    Current pressure: {current_pressure:.4f}<br>
                    Predicted pressure (current moment): {predicted_pressure_now:.4f}<br>
                    Threshold: {threshold:.4f}</p>
                </div>
                """, unsafe_allow_html=True)
            elif system_status == "WARNING":
                breach_message = ""
                if predicted_breach_time:
                    # Ensure breach time is formatted with timezone info
                    breach_message = f"<br><strong>Predicted to reach threshold by: {predicted_breach_time.strftime('%Y-%m-%d %H:%M %Z%z')}</strong>"
                st.markdown(f"""
                <div class="{alert_class}">
                    <h3>⚠️ WARNING</h3>
                    <p><strong>System approaching critical levels.</strong><br>
                    Schedule maintenance within 24 hours.<br>
                    Current pressure: {current_pressure:.4f}{breach_message}</p>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div class="{alert_class}">
                    <h3>✅ SYSTEM OPERATIONAL</h3>
                    <p>All systems operating within normal parameters.<br>
                    Current pressure: {current_pressure:.4f}</p>
                </div>
                """, unsafe_allow_html=True)
            
            # KPI Dashboard
            col1, col2, col3, col4, col5 = st.columns(5)
            
            with col1:
                st.markdown("""
                <div class="metric-card">
                    <h4>System Status</h4>
                    <p class="{}">{}</p>
                </div>
                """.format(status_color, system_status), unsafe_allow_html=True)
            
            with col2:
                st.metric(
                    "Current Pressure", 
                    f"{current_pressure:.4f}",
                    delta=f"{(current_pressure - threshold):.4f}" if current_pressure > threshold else "0.0000"
                )
            
            with col3:
                st.metric(
                    "Model Accuracy (R²)", 
                    f"{r2*100:.1f}%",
                    delta=f"{(r2-0.8)*100:.1f}%" if r2 > 0.8 else None
                )
            
            with col4:
                st.metric(
                    "Prediction Error (MAE)", 
                    f"{mae:.4f}",
                    delta=f"{(mae-0.01):.4f}" if mae > 0.01 else None
                )
            
            with col5:
                maintenance_hours = 24 if system_status == "WARNING" else (0 if system_status == "CRITICAL" else 168)
                st.metric(
                    "Maintenance Window", 
                    f"{maintenance_hours}h",
                    delta="URGENT" if maintenance_hours == 0 else None
                )
            
            # Main visualization
            st.markdown("### 📈 Process Monitoring & Prediction (Including 1-Month Forecast)")
            
            # Create single comprehensive chart
            fig = go.Figure()
            
            # Historical Data (All available data)
            fig.add_trace(
                go.Scatter(
                    x=timestamps_for_chart, 
                    y=ground_truth_for_chart,
                    mode='lines',
                    name='Historical Data',
                    line=dict(color='#2E86AB', width=2),
                    fill='tonexty',
                    fillcolor='rgba(46, 134, 171, 0.1)'
                )
            )
            
            # Predicted values on historical data (overlay on the last part of historical)
            # Ini adalah prediksi pada seluruh data untuk visualisasi, bukan untuk metrik.
            fig.add_trace(
                go.Scatter(
                    x=timestamps_for_all_predictions_viz, 
                    y=predictions_on_all_viz_inv,
                    mode='lines',
                    name='Model Prediction (Historical Viz)',
                    line=dict(color='#A23B72', width=2, dash='dash')
                )
            )

            # Future Predictions (1 Month)
            fig.add_trace(
                go.Scatter(
                    x=future_timestamps,
                    y=future_predictions_inv,
                    mode='lines',
                    name=f'Future Prediction ({future_steps_1_month} steps)',
                    line=dict(color='#00CC96', width=3, dash='dot') # Warna baru untuk prediksi masa depan
                )
            )
            
            # Threshold line
            fig.add_hline(
                y=threshold,
                line_dash="dot",
                line_color="red",
                annotation_text=f"Critical Threshold ({threshold})"
            )
            
            # Update layout
            fig.update_layout(
                height=600,
                showlegend=True,
                title="Industrial Gas Removal System - Process Monitoring & Prediction",
                title_x=0.5,
                title_font_size=20,
                template="plotly_white",
                xaxis_title="Time",
                yaxis_title="Pressure",
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=1.02,
                    xanchor="right",
                    x=1
                ),
                xaxis=dict(tickformat="%Y-%m-%d %H:%M:%S") # Ensure x-axis shows full timestamp
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
            # Performance metrics
            st.markdown("### 📊 Model Performance Analysis")
            
            col1, col2 = st.columns(2)
            
            with col1:
                # Performance metrics table
                metrics_df = pd.DataFrame({
                    'Metric': ['Mean Squared Error (Test)', 'Mean Absolute Error (Test)', 'R² Score (Test)', f'Accuracy (±{accuracy_tolerance}) (Test)'],
                    'Value': [f"{mse:.6f}", f"{mae:.6f}", f"{r2:.4f}", 
                              f"{accuracy:.2f}%"],
                    'Status': ['Good' if mse < 0.001 else 'Acceptable' if mse < 0.01 else 'Poor',
                              'Good' if mae < 0.01 else 'Acceptable' if mae < 0.05 else 'Poor',
                              'Excellent' if r2 > 0.9 else 'Good' if r2 > 0.8 else 'Acceptable',
                              'Excellent' if accuracy > 90 else 'Good'] 
                })
                st.dataframe(metrics_df, use_container_width=True)
            
            with col2:
                # Prediction distribution
                if len(actual_test_inv) > 0:
                    error = np.abs(actual_test_inv - predictions_on_test_inv)
                    fig_dist = go.Figure()
                    fig_dist.add_trace(go.Histogram(
                        x=error,
                        nbinsx=20,
                        name='Error Distribution',
                        marker_color='rgba(46, 134, 171, 0.7)'
                    ))
                    fig_dist.update_layout(
                        title="Prediction Error Distribution (Test Set)",
                        xaxis_title="Absolute Error",
                        yaxis_title="Frequency",
                        template="plotly_white",
                        height=300
                    )
                    st.plotly_chart(fig_dist, use_container_width=True)
                else:
                    st.warning("Not enough data to show error distribution on test set.")
            
            # Data table (if enabled)
            if show_detailed_table:
                st.markdown("### 📋 Detailed Process Data")
                
                # Combine historical and future data for the table
                full_timestamps = timestamps_all + future_timestamps
                full_pressures = ground_truth_all.tolist() + future_predictions_inv.tolist()

                detailed_df = pd.DataFrame({
                    'Timestamp': full_timestamps,
                    'Pressure': full_pressures,
                    'Type': ['Historical'] * len(ground_truth_all) + ['Predicted'] * len(future_predictions_inv),
                    'Status': ['Normal' if p < threshold else 'Critical' for p in full_pressures]
                })
                
                # Format timestamp for display in the table
                detailed_df['Timestamp'] = detailed_df['Timestamp'].dt.strftime('%Y-%m-%d %H:%M:%S %Z%z')

                # Pagination
                if "page_num" not in st.session_state:
                    st.session_state.page_num = 0
                
                rows_per_page = 20
                total_pages = (len(detailed_df) - 1) // rows_per_page + 1
                
                col1_p, col2_p, col3_p = st.columns([1, 2, 1])
                with col1_p:
                    if st.button("← Previous") and st.session_state.page_num > 0:
                        st.session_state.page_num -= 1
                        st.rerun() # Rerun untuk update halaman tabel
                
                with col2_p:
                    st.write(f"Page {st.session_state.page_num + 1} of {total_pages}")
                
                with col3_p:
                    if st.button("Next →") and st.session_state.page_num < total_pages - 1:
                        st.session_state.page_num += 1
                        st.rerun() # Rerun untuk update halaman tabel
                
                start_idx = st.session_state.page_num * rows_per_page
                end_idx = start_idx + rows_per_page
                
                st.dataframe(
                    detailed_df.iloc[start_idx:end_idx],
                    use_container_width=True
                )
            
            # Export functionality
            st.markdown("### 📤 Data Export")
            
            # Untuk export, kita bisa gabungkan hasil prediksi pada test set dengan prediksi masa depan
            # Atau, buat data frame baru yang lebih relevan untuk laporan.
            # Saya akan membuat export_df yang jelas memisahkan historical (aktual) dan prediksi test/future.

            export_df_actual = pd.DataFrame({
                'Timestamp': timestamps_all[:train_size], # Data training historis
                'Pressure_Actual': ground_truth_all[:train_size],
                'Pressure_Predicted_On_Historical': np.nan, # Tidak ada prediksi untuk ini di sini
                'Type': 'Historical_Train',
                'Status': ['Normal' if p < threshold else 'Critical' for p in ground_truth_all[:train_size]]
            })

            export_df_test_pred = pd.DataFrame({
                'Timestamp': test_timestamps,
                'Pressure_Actual': actual_test_inv,
                'Pressure_Predicted_On_Test': predictions_on_test_inv,
                'Absolute_Error_Test': np.abs(actual_test_inv - predictions_on_test_inv),
                'Type': 'Historical_Test_Prediction',
                'Status': ['Normal' if p < threshold else 'Critical' for p in actual_test_inv]
            })

            future_export_df = pd.DataFrame({
                'Timestamp': future_timestamps,
                'Pressure_Actual': np.nan, 
                'Pressure_Predicted_Future': future_predictions_inv,
                'Absolute_Error_Future': np.nan, 
                'Type': 'Future_Prediction',
                'Status': ['Normal' if p < threshold else 'Critical' for p in future_predictions_inv]
            })

            # Gabungkan semua DataFrame
            export_df_combined = pd.concat([export_df_actual, export_df_test_pred, future_export_df], ignore_index=True)
            
            # Format timestamp columns for export
            export_df_combined['Timestamp'] = export_df_combined['Timestamp'].dt.strftime('%Y-%m-%d %H:%M:%S %Z%z')

            col_export_1, col_export_2 = st.columns(2)
            
            with col_export_1:
                csv_data = export_df_combined.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📊 Download Analysis Report (CSV)",
                    data=csv_data,
                    file_name=f"gas_removal_analysis_{get_current_localized_time().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv"
                )
            
            with col_export_2:
                # Generate summary report
                report_text = f"""
Industrial Gas Removal System - Analysis Report
Generated: {get_current_localized_time().strftime('%Y-%m-%d %H:%M:%S %Z%z')}

SYSTEM STATUS: {system_status}
Current Pressure: {current_pressure:.4f}
Critical Threshold: {threshold:.4f}

MODEL PERFORMANCE (On Test Set):
- R² Score: {r2:.4f}
- Mean Absolute Error: {mae:.6f}
- Mean Squared Error: {mse:.6f}
- Accuracy (±{accuracy_tolerance}): {accuracy:.2f}%

DATA SOURCE:
- File: {CSV_FILE_NAME}
- Last Updated: {st.session_state.last_update_time.strftime('%Y-%m-%d %H:%M:%S %Z%z')}
- Auto-Update: {'Enabled' if st.session_state.auto_update_enabled else 'Disabled'}
- Update Interval: {st.session_state.get('selected_interval_label', '3 hours')}

MAINTENANCE RECOMMENDATION:
{
"Immediate maintenance required - System critical!" if system_status == "CRITICAL" else
"Schedule maintenance within 24 hours" + (f" (Predicted breach by: {predicted_breach_time.strftime('%Y-%m-%d %H:%M %Z%z')})" if predicted_breach_time else "") if system_status == "WARNING" else
"No immediate maintenance required"
}
                """
                
                st.download_button(
                    label="📄 Download Summary Report (TXT)",
                    data=report_text,
                    file_name=f"gas_removal_summary_report_{get_current_localized_time().strftime('%Y%m%d_%H%M%S')}.txt",
                    mime="text/plain"
                )

# =============================================================================
# 🚀 MAIN APPLICATION ENTRY POINT
# =============================================================================

def main():
    if not check_authentication():
        login_page()
    else:
        main_dashboard()

if __name__ == "__main__":
    main()
