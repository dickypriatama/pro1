import streamlit as st
import pandas as pd

# ==========================================
# 1. SISTEM LOGIN & HAK AKSES
# ==========================================
# Inisialisasi status login
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.username = ""

# Tampilan Halaman Login
if not st.session_state.logged_in:
    st.title("Halaman Login Dashboard")
    st.write("Silakan masukkan kredensial Anda.")
    
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
            st.session_state.username = username
            st.rerun()
            
        else:
            st.error("Username atau Password salah!")
            
    # Hentikan eksekusi kode di bawah ini jika belum login
    st.stop() 


# ==========================================
# 2. HALAMAN UTAMA DASHBOARD
# ==========================================
# Judul dan Keterangan Last Update
st.title("Dashboard Pagu & Realisasi Satker")
st.caption("last update on 23 Juli 2026")
st.divider()

# ==========================================
# 3. MEMBACA DAN MEMFILTER DATA
# ==========================================
# Membaca data CSV (pastikan file pagu_realisasi.csv ada di folder yang sama)
try:
    df_utama = pd.read_csv("pagu_realisasi.csv.gz")
except FileNotFoundError:
    st.error("File 'pagu_realisasi.csv' tidak ditemukan. Pastikan file berada di folder yang sama dengan app.py.")
    st.stop()

# Memfilter data berdasarkan user yang login
if st.session_state.username != "kanwil04":
    # Asumsi nama kolom di CSV Anda adalah 'kode_satker'
    # Jika berbeda, silakan sesuaikan nama kolomnya di bawah ini
    if 'kode_satker' in df_utama.columns:
        df_utama = df_utama[df_utama['kode_satker'] == st.session_state.username]
    else:
        st.warning("Kolom 'kode_satker' tidak ditemukan pada file CSV. Filter tidak dapat dilakukan.")

# ==========================================
# 4. MENAMPILKAN TABEL DAN REFERENSI
# ==========================================
st.subheader("Data Pagu & Realisasi")

# Membuat tabel agregasi (Contoh sederhana: Menggabungkan data berdasarkan Jenis Belanja)
# Sesuaikan bagian ini dengan logika perhitungan tabel Anda jika diperlukan
try:
    # Contoh pembuatan tabel ringkasan
    df_tabel = df_utama.groupby('jenis_belanja')[['pagu', 'realisasi']].sum().T
    
    # Menambahkan kolom/baris total atau persentase jika diperlukan
    # ... (masukkan logika perhitungan Anda di sini jika ada) ...
    
    # Mengubah nama baris sesuai permintaan
    df_tabel = df_tabel.rename(index={
        "realisasi": "Total Realisasi sd. Saat Ini (Rp)",
        "pagu": "PAGU"
        # Tambahkan "Total Realisasi sd. Saat Ini (%)" di sini jika kolom tersebut Anda buat
    })

    # Fungsi untuk mencetak tebal baris PAGU
    def highlight_pagu(row):
        if row.name == 'PAGU':
            return ['font-weight: bold'] * len(row)
        return [''] * len(row)

    # Menampilkan tabel dengan style
    st.dataframe(df_tabel.style.apply(highlight_pagu, axis=1), use_container_width=True)

except KeyError:
    st.info("Menampilkan raw data karena kolom 'jenis_belanja', 'pagu', atau 'realisasi' tidak ditemukan untuk dibuatkan ringkasan.")
    st.dataframe(df_utama, use_container_width=True)

# Menambahkan referensi Jenis Belanja di bawah tabel
st.caption("""
**Referensi Jenis Belanja:**
*   **51** = Belanja Pegawai | **52** = Belanja Barang | **53** = Belanja Modal
*   **57** = Belanja Bansos | **61** = TKD DBH | **62** = TKD DAU | **63** = TKD DAK Fisik
*   **64** = TKD Insentif Fiskal | **65** = TKD DAK Nonfisik | **66** = TKD Dana Desa
""")
