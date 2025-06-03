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

def init_session_state():
    """Initialize session state variables for auto-update functionality"""
    if 'last_update_time' not in st.session_state:
        st.session_state.last_update_time = datetime.now()
    
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
    current_time = datetime.now()
    time_diff = (current_time - st.session_state.last_update_time).total_seconds()
    
    if time_diff >= st.session_state.update_interval and st.session_state.auto_update_enabled:
        st.session_state.last_update_time = current_time
        # Reset cache pada fungsi load_csv_automatically dengan menambahkan unique_key
        # Ini akan memaksa cache di-invalidate dan fungsi dipanggil ulang
        # Kita bisa juga menghapus cache secara manual dengan load_csv_automatically.clear()
        
        # Untuk Streamlit Cloud, cukup memanggil st.rerun() setelah mengubah
        # last_update_time akan memicu pemanggilan ulang fungsi cached
        # karena timestamp yang di-cache di st.session_state.last_update_time berubah
        st.rerun()

def format_time_remaining():
    """Format waktu yang tersisa sampai update berikutnya"""
    current_time = datetime.now()
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
            st.session_state.last_update_time = datetime.now() # Reset waktu terakhir update
            st.rerun() # Memuat ulang aplikasi
        
        # Show last update time
        st.sidebar.markdown(f"**Last Data Updated:** {st.session_state.last_update_time.strftime('%H:%M:%S')}")
        
        st.sidebar.markdown("---")
        
        # Current CSV file info
        st.sidebar.markdown("### 📄 Data Source")
        st.sidebar.info(f"**CSV File:** {CSV_FILE_NAME}")
        
        if os.path.exists(CSV_FILE_PATH):
            file_size = os.path.getsize(CSV_FILE_PATH) / 1024  # KB
            file_modified = datetime.fromtimestamp(os.path.getmtime(CSV_FILE_PATH))
            st.sidebar.markdown(f"**Size:** {file_size:.2f} KB")
            st.sidebar.markdown(f"**Modified:** {file_modified.strftime('%Y-%m-%d %H:%M:%S')}")
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
    
    # Professional industrial styling
    st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
        
        .main {
            background-color: #f8f9fa;
            font-family: 'Inter', sans-serif;
        }
        
        .main-header {
            background: linear-gradient(90deg, #1e3c72 0%, #2a5298 100%);
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 30px;
            color: white;
            text-align: center;
        }
        
        .kpi-container {
            background: white;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            margin-bottom: 20px;
            border-left: 4px solid #1e3c72;
        }
        
        .alert-critical {
            background-color: #fee;
            border-left: 4px solid #dc3545;
            padding: 15px;
            border-radius: 8px;
            margin: 10px 0;
        }
        
        .alert-warning {
            background-color: #fff3cd;
            border-left: 4px solid #ffc107;
            padding: 15px;
            border-radius: 8px;
            margin: 10px 0;
        }
        
        .alert-normal {
            background-color: #d1edff;
            border-left: 4px solid #28a745;
            padding: 15px;
            border-radius: 8px;
            margin: 10px 0;
        }
        
        .metric-card {
            background: white;
            padding: 15px;
            border-radius: 8px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
            text-align: center;
        }
        
        .status-operational {
            color: #28a745;
            font-weight: 600;
        }
        
        .status-warning {
            color: #ffc107;
            font-weight: 600;
        }
        
        .status-critical {
            color: #dc3545;
            font-weight: 600;
        }
        
        .stPlotlyChart {
            background: white;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            margin-bottom: 20px;
        }
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
        default_start_date = datetime.now().date() - timedelta(days=7)
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
                    '%d-%m-%Y %H:%M', '%m/%d/%Y %H:%M'
                ]
                
                parsed_dates = None
                for date_format in date_formats:
                    try:
                        parsed_dates = pd.to_datetime(df[timestamp_col], format=date_format)
                        break
                    except Exception:
                        continue
                
                if parsed_dates is None:
                    try:
                        parsed_dates = pd.to_datetime(df[timestamp_col])
                    except Exception:
                        # Fallback jika parsing otomatis gagal
                        st.sidebar.warning("⚠️ Could not parse timestamp column. Generating timestamps.")
                        parsed_dates = pd.date_range(start=start_date, periods=len(df), freq='H')
                
                df['timestamp'] = parsed_dates
            else:
                df['timestamp'] = pd.date_range(start=start_date, periods=len(df), freq='H')
                st.sidebar.warning("⚠️ No timestamp column found. Using generated timestamps.")
            
            # Clean and prepare data
            data = df[[pressure_col]].copy()
            data = data.apply(lambda x: pd.to_numeric(x.astype(str).str.replace(',', '.'), errors='coerce'))
            data = data.dropna()
            
            # Remove negative values
            if (data < 0).any().any():
                st.sidebar.warning("⚠️ Negative values detected and clipped to zero.")
                data = data.clip(lower=0)
            
            ground_truth = data.values.flatten()
            timestamps = df['timestamp'].iloc[:len(ground_truth)].tolist()
            
            # Scaling
            scaler = MinMaxScaler(feature_range=(0, 1))
            scaled_data = scaler.fit_transform(data)
            
            # Create sequences for LSTM
            def create_sequences(data, seq_length):
                sequences = []
                for i in range(len(data) - seq_length):
                    sequences.append(data[i:i+seq_length])
                return np.array(sequences)
            
            X = create_sequences(scaled_data, sequence_length)
            
            if len(X) == 0:
                st.error("❌ Insufficient data for analysis. Please check your CSV file or reduce sequence length.")
                st.stop()
            
            # Predictions
            predictions = model.predict(X)
            predictions_inv = scaler.inverse_transform(predictions).flatten()
            
            # Train/test split (adjusting for sequence_length offset)
            # Prediksi selalu lebih pendek dari ground_truth karena windowing
            # Kita perlu menyelaraskan indeks waktu
            
            # Timestamp untuk prediksi dimulai setelah sequence_length pertama
            pred_timestamps = timestamps[sequence_length:]
            
            # Ground truth yang sesuai dengan prediksi
            ground_truth_for_preds = ground_truth[sequence_length:]
            
            # Ambil semua data yang digunakan untuk prediksi dan ground truth yang sesuai
            actual_test = ground_truth_for_preds
            pred_test = predictions_inv
            
            # Pastikan panjangnya sama
            if len(actual_test) != len(pred_test):
                min_len = min(len(actual_test), len(pred_test))
                actual_test = actual_test[:min_len]
                pred_test = pred_test[:min_len]
                pred_timestamps = pred_timestamps[:min_len]
                st.sidebar.warning("Adjusted prediction/actual array lengths due to mismatch.")
            
            # Calculate metrics
            if len(actual_test) > 0:
                mse = mean_squared_error(actual_test, pred_test)
                mae = mean_absolute_error(actual_test, pred_test)
                r2 = r2_score(actual_test, pred_test)
            else:
                mse, mae, r2 = 0, 0, 0
                st.warning("Not enough data to calculate performance metrics.")
                
            # System status determination
            current_pressure = ground_truth[-1] if len(ground_truth) > 0 else 0
            predicted_pressure = predictions_inv[-1] if len(predictions_inv) > 0 else 0
            
            if current_pressure > threshold or predicted_pressure > threshold:
                system_status = "CRITICAL"
                status_color = "status-critical"
                alert_class = "alert-critical"
            elif current_pressure > threshold * 0.8 or predicted_pressure > threshold * 0.8:
                system_status = "WARNING"
                status_color = "status-warning"
                alert_class = "alert-warning"
            else:
                system_status = "OPERATIONAL"
                status_color = "status-operational"
                alert_class = "alert-normal"
            
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
                    Predicted pressure: {predicted_pressure:.4f}<br>
                    Threshold: {threshold:.4f}</p>
                </div>
                """, unsafe_allow_html=True)
            elif system_status == "WARNING":
                st.markdown(f"""
                <div class="{alert_class}">
                    <h3>⚠️ WARNING</h3>
                    <p><strong>System approaching critical levels.</strong><br>
                    Schedule maintenance within 24 hours.<br>
                    Current pressure: {current_pressure:.4f}</p>
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
            st.markdown("### 📈 Process Monitoring & Prediction")
            
            # Create single comprehensive chart
            fig = go.Figure()
            
            # Historical data (hingga titik awal prediksi)
            fig.add_trace(
                go.Scatter(
                    x=timestamps[:sequence_length], # Data yang digunakan untuk melatih/melihat masa lalu
                    y=ground_truth[:sequence_length],
                    mode='lines',
                    name='Historical Data',
                    line=dict(color='#2E86AB', width=2),
                    fill='tonexty',
                    fillcolor='rgba(46, 134, 171, 0.1)'
                )
            )
            
            # Predicted values
            fig.add_trace(
                go.Scatter(
                    x=pred_timestamps, # Gunakan timestamps yang diselaraskan untuk prediksi
                    y=pred_test,
                    mode='lines',
                    name='Predicted Values',
                    line=dict(color='#A23B72', width=3, dash='dash')
                )
            )
            
            # Actual values (yang sesuai dengan prediksi)
            fig.add_trace(
                go.Scatter(
                    x=pred_timestamps, # Gunakan timestamps yang diselaraskan untuk aktual
                    y=actual_test,
                    mode='lines',
                    name='Actual Values',
                    line=dict(color='#F18F01', width=2)
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
                )
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
            # Performance metrics
            st.markdown("### 📊 Model Performance Analysis")
            
            col1, col2 = st.columns(2)
            
            with col1:
                # Performance metrics table
                metrics_df = pd.DataFrame({
                    'Metric': ['Mean Squared Error', 'Mean Absolute Error', 'R² Score', 'Accuracy (±0.01)'],
                    'Value': [f"{mse:.6f}", f"{mae:.6f}", f"{r2:.4f}", 
                              f"{np.mean(np.abs(actual_test - pred_test) <= 0.01)*100:.2f}%" if len(actual_test) > 0 else "N/A"],
                    'Status': ['Good' if mse < 0.001 else 'Acceptable' if mse < 0.01 else 'Poor',
                              'Good' if mae < 0.01 else 'Acceptable' if mae < 0.05 else 'Poor',
                              'Excellent' if r2 > 0.9 else 'Good' if r2 > 0.8 else 'Acceptable',
                              'Excellent' if np.mean(np.abs(actual_test - pred_test) <= 0.01)*100 > 90 else 'Good'] if len(actual_test) > 0 else ['N/A', 'N/A', 'N/A', 'N/A']
                })
                st.dataframe(metrics_df, use_container_width=True)
            
            with col2:
                # Prediction distribution
                if len(actual_test) > 0:
                    error = np.abs(actual_test - pred_test)
                    fig_dist = go.Figure()
                    fig_dist.add_trace(go.Histogram(
                        x=error,
                        nbinsx=20,
                        name='Error Distribution',
                        marker_color='rgba(46, 134, 171, 0.7)'
                    ))
                    fig_dist.update_layout(
                        title="Prediction Error Distribution",
                        xaxis_title="Absolute Error",
                        yaxis_title="Frequency",
                        template="plotly_white",
                        height=300
                    )
                    st.plotly_chart(fig_dist, use_container_width=True)
                else:
                    st.warning("Not enough data to show error distribution.")
            
            # Data table (if enabled)
            if show_detailed_table:
                st.markdown("### 📋 Detailed Process Data")
                
                detailed_df = pd.DataFrame({
                    'Timestamp': timestamps,
                    'Pressure': ground_truth,
                    'Status': ['Normal' if p < threshold else 'Critical' for p in ground_truth]
                })
                
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
            
            export_df = pd.DataFrame({
                'Timestamp': pred_timestamps,
                'Actual_Pressure': actual_test,
                'Predicted_Pressure': pred_test,
                'Absolute_Error': np.abs(actual_test - pred_test),
                'Status': ['Critical' if p > threshold else 'Normal' for p in actual_test]
            })
            
            col_export_1, col_export_2 = st.columns(2)
            
            with col_export_1:
                csv_data = export_df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📊 Download Analysis Report (CSV)",
                    data=csv_data,
                    file_name=f"gas_removal_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv"
                )
            
            with col_export_2:
                # Generate summary report
                report_text = f"""
Industrial Gas Removal System - Analysis Report
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

SYSTEM STATUS: {system_status}
Current Pressure: {current_pressure:.4f}
Critical Threshold: {threshold:.4f}

MODEL PERFORMANCE:
- R² Score: {r2:.4f}
- Mean Absolute Error: {mae:.6f}
- Mean Squared Error: {mse:.6f}

DATA SOURCE:
- File: {CSV_FILE_NAME}
- Last Updated: {st.session_state.last_update_time.strftime('%Y-%m-%d %H:%M:%S')}
- Auto-Update: {'Enabled' if st.session_state.auto_update_enabled else 'Disabled'}
- Update Interval: {st.session_state.get('selected_interval_label', '3 hours')}

MAINTENANCE RECOMMENDATION:
{
"Immediate maintenance required - System critical!" if system_status == "CRITICAL" else
"Schedule maintenance within 24 hours" if system_status == "WARNING" else
"No immediate maintenance required"
}
                """
                
                st.download_button(
                    label="📄 Download Summary Report (TXT)",
                    data=report_text,
                    file_name=f"gas_removal_summary_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
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
