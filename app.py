"""
Dashboard Pagu & Realisasi Satker
----------------------------------
Streamlit + Groq (narasi & chat AI). Supabase opsional untuk sumber data terpusat
(lihat README.md, bagian "Pakai Supabase sebagai sumber data").
"""

import os
from datetime import date

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from groq import Groq

# --------------------------------------------------------------------------
# Konfigurasi dasar
# --------------------------------------------------------------------------

st.set_page_config(
    page_title="Dashboard Pagu & Realisasi Satker",
    page_icon="📊",
    layout="wide",
)

BULAN_KOLOM = ["JAN", "FEB", "MAR", "APR", "MEI", "JUN",
               "JUL", "AGS", "SEP", "OKT", "NOV", "DES"]
BULAN_LABEL = {i + 1: b for i, b in enumerate(BULAN_KOLOM)}

GROQ_MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")


# --------------------------------------------------------------------------
# Load data
# --------------------------------------------------------------------------

@st.cache_data(show_spinner="Memuat data...")
def load_data_from_csv(path: str) -> pd.DataFrame:
    return pd.read_csv(path)


@st.cache_data(show_spinner="Memuat data dari Supabase...")
def load_data_from_supabase(url: str, key: str, table: str) -> pd.DataFrame:
    from supabase import create_client

    client = create_client(url, key)
    all_rows, page, page_size = [], 0, 1000
    while True:
        resp = (
            client.table(table)
            .select("*")
            .range(page * page_size, (page + 1) * page_size - 1)
            .execute()
        )
        rows = resp.data
        all_rows.extend(rows)
        if len(rows) < page_size:
            break
        page += 1
    return pd.DataFrame(all_rows)


def load_data() -> pd.DataFrame:
    use_supabase = st.secrets.get("USE_SUPABASE", "false") == "true" if hasattr(st, "secrets") else False
    if use_supabase:
        return load_data_from_supabase(
            st.secrets["SUPABASE_URL"],
            st.secrets["SUPABASE_KEY"],
            st.secrets.get("SUPABASE_TABLE", "pagu_realisasi"),
        )
    return load_data_from_csv("data/pagu_realisasi.csv")


df = load_data()

# Kolom REALISASI & SISA PAGU dihitung ulang dari total kolom bulanan (JAN..DES).
# Ini supaya semua angka di dashboard konsisten dengan rincian bulanannya -- pada sebagian
# data sumber, kolom REALISASI bawaan bisa tidak sinkron dengan rincian JAN..DES-nya.
df["REALISASI"] = df[BULAN_KOLOM].sum(axis=1)
df["SISA PAGU"] = df["PAGU"] - df["REALISASI"]


# --------------------------------------------------------------------------
# Sidebar - filter
# --------------------------------------------------------------------------

st.sidebar.header("Filter")

tahun_list = sorted(df["TAHUN"].unique(), reverse=True)
tahun = st.sidebar.selectbox("Tahun", tahun_list)

df_tahun = df[df["TAHUN"] == tahun]

SEMUA_DEPT = "— Semua Kementerian/Lembaga —"
SEMUA_SATKER = "— Semua Satker —"

dept_options = (
    df_tahun[["KDDEPT", "NMDEPT"]]
    .drop_duplicates()
    .sort_values("KDDEPT")
)
dept_options["LABEL"] = dept_options["KDDEPT"].astype(str) + " - " + dept_options["NMDEPT"]
dept_label = st.sidebar.selectbox("Kementerian/Lembaga", [SEMUA_DEPT] + dept_options["LABEL"].tolist())

if dept_label == SEMUA_DEPT:
    kddept = None
    nmdept = "Semua Kementerian/Lembaga"
    df_dept = df_tahun
else:
    kddept = int(dept_label.split(" - ")[0])
    nmdept = dept_options.loc[dept_options["KDDEPT"] == kddept, "NMDEPT"].iloc[0]
    df_dept = df_tahun[df_tahun["KDDEPT"] == kddept]

satker_options = (
    df_dept[["KDSATKER", "NMSATKER"]]
    .drop_duplicates()
    .sort_values("KDSATKER")
)
satker_options["LABEL"] = satker_options["KDSATKER"].astype(str) + " - " + satker_options["NMSATKER"]
satker_label = st.sidebar.selectbox("Satuan Kerja (Satker)", [SEMUA_SATKER] + satker_options["LABEL"].tolist())

if satker_label == SEMUA_SATKER:
    kdsatker = None
    nmsatker = "Semua Satker"
    df_satker = df_dept
else:
    kdsatker = int(satker_label.split(" - ")[0])
    nmsatker = satker_options.loc[satker_options["KDSATKER"] == kdsatker, "NMSATKER"].iloc[0]
    df_satker = df_dept[df_dept["KDSATKER"] == kdsatker]


# --------------------------------------------------------------------------
# Agregasi
# --------------------------------------------------------------------------

pagu_total = df_satker["PAGU"].sum()
realisasi_total = df_satker["REALISASI"].sum()
sisa_pagu = df_satker["SISA PAGU"].sum()
persen_serapan = (realisasi_total / pagu_total * 100) if pagu_total else 0

monthly = df_satker[BULAN_KOLOM].sum()
kumulatif = monthly.cumsum()

# bulan terakhir yang punya realisasi (>0)
bulan_terisi = [i + 1 for i, v in enumerate(monthly.values) if v != 0]
bulan_terakhir = max(bulan_terisi) if bulan_terisi else 0

if bulan_terakhir > 0:
    rerata_bulanan = kumulatif.iloc[bulan_terakhir - 1] / bulan_terakhir
    proyeksi_akhir_tahun = rerata_bulanan * 12
else:
    rerata_bulanan = 0
    proyeksi_akhir_tahun = 0

persen_proyeksi = (proyeksi_akhir_tahun / pagu_total * 100) if pagu_total else 0

jenis_belanja = (
    df_satker.groupby("LABEL_JENIS_BELANJA")["REALISASI"]
    .sum()
    .sort_values(ascending=False)
    .reset_index()
)


# --------------------------------------------------------------------------
# Header & KPI
# --------------------------------------------------------------------------

st.title("📊 Dashboard Pagu & Realisasi Satker")
st.caption(f"{nmdept} — {nmsatker} — Tahun {tahun}")


def kpi_card(label: str, value: str, delta: str = None):
    delta_html = (
        f'<div style="font-size:0.85rem;color:#16a34a;margin-top:4px;">{delta}</div>'
        if delta else ""
    )
    st.markdown(
        f"""
        <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:12px;
                    padding:16px 18px;min-height:110px;">
            <div style="font-size:0.85rem;color:#64748b;margin-bottom:6px;">{label}</div>
            <div style="font-size:clamp(1rem, 2.1vw, 1.6rem);font-weight:700;color:#0f172a;
                        white-space:normal;overflow-wrap:break-word;line-height:1.25;">{value}</div>
            {delta_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


r1c1, r1c2 = st.columns(2)
r2c1, r2c2 = st.columns(2)

with r1c1:
    kpi_card("Pagu", f"Rp {pagu_total:,.0f}")
with r1c2:
    kpi_card("Realisasi", f"Rp {realisasi_total:,.0f}", f"{persen_serapan:.1f}% dari pagu")
with r2c1:
    kpi_card("Sisa Pagu", f"Rp {sisa_pagu:,.0f}")
with r2c2:
    kpi_card(
        "Proyeksi Realisasi Akhir Tahun",
        f"Rp {proyeksi_akhir_tahun:,.0f}",
        f"{persen_proyeksi:.1f}% dari pagu",
    )

st.divider()

# --------------------------------------------------------------------------
# Grafik batang: Pagu vs Realisasi per bulan (kumulatif) + Grafik batang total
# --------------------------------------------------------------------------

col1, col2 = st.columns([3, 2])

with col1:
    st.subheader("Realisasi per Bulan")
    bar_df = pd.DataFrame({"Bulan": BULAN_KOLOM, "Realisasi": monthly.values})
    fig_bar = px.bar(bar_df, x="Bulan", y="Realisasi", text_auto=".2s")
    fig_bar.update_layout(yaxis_title="Rupiah", xaxis_title=None)
    st.plotly_chart(fig_bar, use_container_width=True)

with col2:
    st.subheader("Pagu vs Realisasi")
    fig_pv = go.Figure(data=[
        go.Bar(name="Pagu", x=["Total"], y=[pagu_total]),
        go.Bar(name="Realisasi", x=["Total"], y=[realisasi_total]),
    ])
    fig_pv.update_layout(barmode="group", yaxis_title="Rupiah")
    st.plotly_chart(fig_pv, use_container_width=True)


# --------------------------------------------------------------------------
# Pie charts
# --------------------------------------------------------------------------

st.subheader("Komposisi")
p1, p2 = st.columns(2)

with p1:
    st.caption("Realisasi vs Sisa Pagu")
    fig_pie1 = px.pie(
        names=["Realisasi", "Sisa Pagu"],
        values=[realisasi_total, max(sisa_pagu, 0)],
        hole=0.4,
    )
    st.plotly_chart(fig_pie1, use_container_width=True)

with p2:
    st.caption("Realisasi per Jenis Belanja")
    fig_pie2 = px.pie(jenis_belanja, names="LABEL_JENIS_BELANJA", values="REALISASI", hole=0.4)
    st.plotly_chart(fig_pie2, use_container_width=True)


# --------------------------------------------------------------------------
# Trendline proyeksi
# --------------------------------------------------------------------------

st.subheader("Tren & Proyeksi Realisasi hingga Akhir Tahun")

bulan_angka = list(range(1, 13))

# Grafik non-kumulatif: nilai realisasi per bulan (biar kelihatan naik-turunnya),
# bulan setelah bulan_terakhir ditampilkan sebagai proyeksi rata-rata (garis putus-putus)
aktual = [monthly.values[b - 1] if b <= bulan_terakhir else None for b in bulan_angka]
proyeksi = []
for b in bulan_angka:
    if bulan_terakhir == 0:
        proyeksi.append(None)
    elif b < bulan_terakhir:
        proyeksi.append(None)
    elif b == bulan_terakhir:
        proyeksi.append(monthly.values[b - 1])  # titik sambung dengan garis aktual
    else:
        proyeksi.append(rerata_bulanan)

fig_trend = go.Figure()
fig_trend.add_trace(go.Scatter(
    x=BULAN_KOLOM, y=aktual, mode="lines+markers",
    name="Realisasi per Bulan (Aktual)", line=dict(width=3),
))
fig_trend.add_trace(go.Scatter(
    x=BULAN_KOLOM, y=proyeksi, mode="lines+markers",
    name="Proyeksi (rata-rata bulanan)", line=dict(dash="dash"),
))
fig_trend.update_layout(yaxis_title="Rupiah (per bulan)", xaxis_title=None)
st.plotly_chart(fig_trend, use_container_width=True)

st.caption(
    "Grafik ini menampilkan realisasi tiap bulan (bukan kumulatif) supaya terlihat bulan mana "
    "yang realisasinya naik/turun. Bulan setelah "
    f"{BULAN_LABEL.get(bulan_terakhir, '-')} adalah proyeksi memakai rata-rata realisasi bulan "
    "berjalan — estimasi sederhana, bukan angka resmi."
)

# --------------------------------------------------------------------------
# Tabel realisasi per bulan per jenis belanja (aktual vs proyeksi)
# --------------------------------------------------------------------------

st.markdown("**Pagu & Realisasi per Bulan per Jenis Belanja**")

TOTAL_COL = "TOTAL (Realisasi+Proyeksi)"

# Urutan baris tabel mengikuti kode jenis belanja (51 Pegawai, 52 Barang, 53 Modal, dst),
# bukan diurutkan berdasarkan besar realisasi seperti pie chart.
urutan_kode = (
    df_satker[["JENIS BELANJA", "LABEL_JENIS_BELANJA"]]
    .drop_duplicates()
    .sort_values("JENIS BELANJA")["LABEL_JENIS_BELANJA"]
    .tolist()
)

pagu_per_jenis = (
    df_satker.groupby("LABEL_JENIS_BELANJA")["PAGU"].sum()
    .reindex(urutan_kode)
)

tabel = df_satker.groupby("LABEL_JENIS_BELANJA")[BULAN_KOLOM].sum().astype(float)
tabel = tabel.reindex(urutan_kode)  # urutkan sesuai kode jenis belanja

mask_proyeksi = pd.DataFrame(False, index=tabel.index, columns=BULAN_KOLOM)
if bulan_terakhir < 12:
    for jb in tabel.index:
        actual_sum = tabel.loc[jb, BULAN_KOLOM[:bulan_terakhir]].sum() if bulan_terakhir else 0
        rerata_jb = actual_sum / bulan_terakhir if bulan_terakhir else 0
        for m in range(bulan_terakhir, 12):
            tabel.loc[jb, BULAN_KOLOM[m]] = rerata_jb
    mask_proyeksi.loc[:, BULAN_KOLOM[bulan_terakhir:]] = True

tabel.loc["Total"] = tabel.sum()
mask_proyeksi.loc["Total"] = mask_proyeksi.iloc[0] if len(mask_proyeksi) else False

# Kolom PAGU (disisipkan sebelum kolom bulanan) dan kolom TOTAL (realisasi+proyeksi) di akhir
tabel.insert(0, "PAGU", pd.concat([pagu_per_jenis, pd.Series({"Total": pagu_total})]))
tabel[TOTAL_COL] = tabel[BULAN_KOLOM].sum(axis=1)

# Mask lengkap (PAGU & TOTAL_COL tidak pernah ditandai sebagai proyeksi)
mask_lengkap = pd.DataFrame(False, index=tabel.index, columns=tabel.columns)
mask_lengkap[BULAN_KOLOM] = mask_proyeksi[BULAN_KOLOM]


def _highlight_proyeksi(_):
    return pd.DataFrame(
        np.where(mask_lengkap, "background-color: #fff3cd; color: #7a5b00;", ""),
        index=mask_lengkap.index, columns=mask_lengkap.columns,
    )


styled_tabel = (
    tabel.style
    .apply(_highlight_proyeksi, axis=None)
    .format("Rp {:,.0f}")
)
st.dataframe(styled_tabel, use_container_width=True)
st.caption(
    "🟨 Sel berwarna kuning = angka proyeksi (belum realisasi aktual), dihitung dari rata-rata "
    "realisasi per jenis belanja pada bulan-bulan yang sudah berjalan. Kolom PAGU dan kolom "
    f"\"{TOTAL_COL}\" tidak ditandai kuning karena berupa gabungan/acuan, bukan proyeksi murni."
)

st.divider()


# --------------------------------------------------------------------------
# Groq helper
# --------------------------------------------------------------------------

def get_groq_client():
    api_key = st.secrets.get("GROQ_API_KEY") if hasattr(st, "secrets") else None
    api_key = api_key or os.environ.get("GROQ_API_KEY")
    if not api_key:
        return None
    return Groq(api_key=api_key)


def ringkasan_data_untuk_ai() -> str:
    top3_jenis = jenis_belanja.head(3)
    baris_jenis = "\n".join(
        f"- {row.LABEL_JENIS_BELANJA}: Rp {row.REALISASI:,.0f}"
        for row in top3_jenis.itertuples()
    )
    kddept_ket = f" (kode {kddept})" if kddept is not None else ""
    kdsatker_ket = f" (kode {kdsatker})" if kdsatker is not None else ""
    return f"""
Data satker:
- Kementerian/Lembaga: {nmdept}{kddept_ket}
- Satker: {nmsatker}{kdsatker_ket}
- Tahun: {tahun}
- Pagu: Rp {pagu_total:,.0f}
- Realisasi sampai bulan {BULAN_LABEL.get(bulan_terakhir, '-')}: Rp {realisasi_total:,.0f} ({persen_serapan:.1f}% dari pagu)
- Sisa pagu: Rp {sisa_pagu:,.0f}
- Proyeksi realisasi akhir tahun: Rp {proyeksi_akhir_tahun:,.0f} ({persen_proyeksi:.1f}% dari pagu)
- 3 jenis belanja dengan realisasi terbesar:
{baris_jenis}
""".strip()


# --------------------------------------------------------------------------
# Narasi otomatis AI
# --------------------------------------------------------------------------

st.subheader("🤖 Narasi Otomatis")

client = get_groq_client()

if client is None:
    st.info(
        "Narasi AI belum aktif. Tambahkan `GROQ_API_KEY` di file `.streamlit/secrets.toml` "
        "(lihat README.md) untuk mengaktifkan fitur ini."
    )
else:
    cache_key = f"narasi_{tahun}_{kddept}_{kdsatker}"
    if st.button("Buat / Perbarui Narasi", key=f"btn_{cache_key}"):
        with st.spinner("AI sedang menyusun narasi..."):
            resp = client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Kamu adalah analis anggaran pemerintah Indonesia. Tulis narasi singkat "
                            "(1-2 paragraf, bahasa Indonesia formal) yang menjelaskan kondisi pagu dan "
                            "realisasi anggaran satker berikut, termasuk kecukupan serapan dan proyeksi "
                            "akhir tahun. Jangan mengulang angka mentah secara berlebihan, fokus pada insight."
                        ),
                    },
                    {"role": "user", "content": ringkasan_data_untuk_ai()},
                ],
            )
            st.session_state[cache_key] = resp.choices[0].message.content

    if cache_key in st.session_state:
        st.write(st.session_state[cache_key])
    else:
        st.caption("Klik tombol di atas untuk membuat narasi.")


st.divider()


# --------------------------------------------------------------------------
# Chat box bebas
# --------------------------------------------------------------------------

st.subheader("💬 Tanya AI tentang Data Ini")

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

for msg in st.session_state.chat_history:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

prompt = st.chat_input("Tulis pertanyaan tentang pagu/realisasi satker ini...")

if prompt:
    st.session_state.chat_history.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.write(prompt)

    if client is None:
        jawaban = "Fitur chat AI belum aktif karena GROQ_API_KEY belum di-set. Lihat README.md."
    else:
        with st.spinner("AI sedang menjawab..."):
            messages = [
                {
                    "role": "system",
                    "content": (
                        "Kamu adalah asisten analisis anggaran pemerintah Indonesia. Jawab pertanyaan "
                        "pengguna berdasarkan data satker berikut. Jika pertanyaan di luar cakupan data, "
                        "katakan dengan jujur bahwa datanya tidak tersedia.\n\n" + ringkasan_data_untuk_ai()
                    ),
                }
            ] + st.session_state.chat_history

            resp = client.chat.completions.create(model=GROQ_MODEL, messages=messages)
            jawaban = resp.choices[0].message.content

    st.session_state.chat_history.append({"role": "assistant", "content": jawaban})
    with st.chat_message("assistant"):
        st.write(jawaban)
