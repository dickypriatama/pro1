import streamlit as st
import pandas as pd

# ==========================================
# 1. SISTEM LOGIN & HAK AKSES
# ==========================================
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.username = ""

if not st.session_state.logged_in:
    st.title("Halaman Login Dashboard")
    
    username = st.text_input("Username (Kode Satker atau 'kanwil04')")
    password = st.text_input("Password", type="password")
    
    if st.button("Login"):
        # Logika Super User
        if username == "kanwil04" and password == "kanwil04":
            st.session_state.logged_in = True
            st.session_state.username = username
            st.rerun()
            
        # Logika User Satker (Username = Password)
        elif username == password and username.strip() != "":
            st.session_state.logged_in = True
            st.session_state.username = username.strip()
            st.rerun()
            
        else:
            st.error("Username atau Password salah!")
            
    st.stop() 


# ==========================================
# 2. HALAMAN UTAMA DASHBOARD
# ==========================================
st.title("Dashboard Pagu & Realisasi Satker")
st.caption("last update on 23 Juli 2026")
st.divider()

# ==========================================
# 3. MEMBACA & MENYESUAIKAN DATA CSV
# ==========================================
try:
    df_utama = pd.read_csv("pagu_realisasi.csv")
    
    # STANDARISASI: Menjadikan semua nama kolom huruf kecil dan menghapus spasi
    # Ini mencegah error akibat perbedaan penulisan seperti KODE_SATKER atau Pagu
    df_utama.columns = df_utama.columns.str.lower().str.strip()
    
except FileNotFoundError:
    st.error("File 'pagu_realisasi.csv' tidak ditemukan. Pastikan ada di folder yang sama!")
    st.stop()

# ==========================================
# 4. FILTER DATA (HAK AKSES)
# ==========================================
if st.session_state.username != "kanwil04":
    
    # Mengecek apakah ada kolom untuk satker (bisa 'kode_satker' atau 'satker')
    kolom_satker = None
    if 'kode_satker' in df_utama.columns:
        kolom_satker = 'kode_satker'
    elif 'satker' in df_utama.columns:
        kolom_satker = 'satker'
        
    if kolom_satker:
        # PENTING: Ubah data di kolom satker menjadi teks (string) agar sama dengan input form login
        df_utama[kolom_satker] = df_utama[kolom_satker].astype(str).str.strip()
        
        # Eksekusi filter
        df_utama = df_utama[df_utama[kolom_satker] == st.session_state.username]
        
        # Cek jika data kosong setelah difilter
        if df_utama.empty:
            st.error(f"Data tidak ditemukan untuk satker kode: {st.session_state.username}.")
            st.info("Apakah kodenya sudah benar? Cek kembali data di CSV Anda.")
            st.stop()
    else:
        st.error("Gagal melakukan filter. Kolom untuk kode satker tidak ditemukan.")
        st.info(f"Kolom yang terdeteksi di CSV Anda: {', '.join(df_utama.columns)}")
        st.stop()

# ==========================================
# 5. MENAMPILKAN TABEL DASHBOARD
# ==========================================
st.subheader("Data Pagu & Realisasi")

try:
    # Memastikan kolom perhitungan adalah angka murni
    df_utama['pagu'] = pd.to_numeric(df_utama['pagu'], errors='coerce').fillna(0)
    df_utama['realisasi'] = pd.to_numeric(df_utama['realisasi'], errors='coerce').fillna(0)
    
    # Pengelompokkan berdasarkan jenis belanja
    df_tabel = df_utama.groupby('jenis_belanja')[['pagu', 'realisasi']].sum().T
    
    # Mengganti nama baris
    df_tabel = df_tabel.rename(index={
        "realisasi": "Total Realisasi sd. Saat Ini (Rp)",
        "pagu": "PAGU"
    })

    # Fungsi untuk menebalkan (bold) baris PAGU
    def highlight_pagu(row):
        if row.name == 'PAGU':
            return ['font-weight: bold'] * len(row)
        return [''] * len(row)

    # Tampilkan tabel
    st.dataframe(df_tabel.style.apply(highlight_pagu, axis=1), use_container_width=True)

except KeyError:
    # Jika gagal mengelompokkan (karena nama kolom berbeda), tampilkan data mentahnya saja
    st.warning("Gagal membuat tabel ringkasan karena kolom 'jenis_belanja', 'pagu', atau 'realisasi' tidak ditemukan di CSV.")
    st.info(f"Kolom yang ada di CSV Anda: {', '.join(df_utama.columns)}")
    st.dataframe(df_utama, use_container_width=True)

# Teks keterangan referensi
st.caption("""
**Referensi Jenis Belanja:**
*   **51** = Belanja Pegawai | **52** = Belanja Barang | **53** = Belanja Modal
*   **57** = Belanja Bansos | **61** = TKD DBH | **62** = TKD DAU | **63** = TKD DAK Fisik
*   **64** = TKD Insentif Fiskal | **65** = TKD DAK Nonfisik | **66** = TKD Dana Desa
""")