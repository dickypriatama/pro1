"""
Dashboard Pagu & Realisasi Satker
----------------------------------
Streamlit + Groq (narasi & chat AI). Supabase opsional untuk sumber data terpusat
(lihat README.md, bagian "Pakai Supabase sebagai sumber data").
"""

import os
from datetime import date

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


# --------------------------------------------------------------------------
# Sidebar - filter
# --------------------------------------------------------------------------

st.sidebar.header("Filter")

tahun_list = sorted(df["TAHUN"].unique(), reverse=True)
tahun = st.sidebar.selectbox("Tahun", tahun_list)

df_tahun = df[df["TAHUN"] == tahun]

dept_options = (
    df_tahun[["KDDEPT", "NMDEPT"]]
    .drop_duplicates()
    .sort_values("KDDEPT")
)
dept_options["LABEL"] = dept_options["KDDEPT"].astype(str) + " - " + dept_options["NMDEPT"]
dept_label = st.sidebar.selectbox("Kementerian/Lembaga", dept_options["LABEL"])
kddept = int(dept_label.split(" - ")[0])

df_dept = df_tahun[df_tahun["KDDEPT"] == kddept]

satker_options = (
    df_dept[["KDSATKER", "NMSATKER"]]
    .drop_duplicates()
    .sort_values("KDSATKER")
)
satker_options["LABEL"] = satker_options["KDSATKER"].astype(str) + " - " + satker_options["NMSATKER"]
satker_label = st.sidebar.selectbox("Satuan Kerja (Satker)", satker_options["LABEL"])
kdsatker = int(satker_label.split(" - ")[0])

df_satker = df_dept[df_dept["KDSATKER"] == kdsatker]

nmdept = dept_options.loc[dept_options["KDDEPT"] == kddept, "NMDEPT"].iloc[0]
nmsatker = satker_options.loc[satker_options["KDSATKER"] == kdsatker, "NMSATKER"].iloc[0]


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

k1, k2, k3, k4 = st.columns(4)
k1.metric("Pagu", f"Rp {pagu_total:,.0f}")
k2.metric("Realisasi", f"Rp {realisasi_total:,.0f}", f"{persen_serapan:.1f}% dari pagu")
k3.metric("Sisa Pagu", f"Rp {sisa_pagu:,.0f}")
k4.metric(
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
aktual = [kumulatif.iloc[b - 1] if b <= bulan_terakhir else None for b in bulan_angka]
proyeksi = [
    None if b < bulan_terakhir else
    (kumulatif.iloc[bulan_terakhir - 1] + rerata_bulanan * (b - bulan_terakhir) if bulan_terakhir else None)
    for b in bulan_angka
]

fig_trend = go.Figure()
fig_trend.add_trace(go.Scatter(x=BULAN_KOLOM, y=aktual, mode="lines+markers", name="Realisasi Kumulatif (Aktual)"))
fig_trend.add_trace(go.Scatter(x=BULAN_KOLOM, y=proyeksi, mode="lines+markers", name="Proyeksi", line=dict(dash="dash")))
fig_trend.add_hline(y=pagu_total, line_dash="dot", annotation_text="Pagu", line_color="gray")
fig_trend.update_layout(yaxis_title="Rupiah (kumulatif)", xaxis_title=None)
st.plotly_chart(fig_trend, use_container_width=True)

st.caption(
    "Metode proyeksi: rata-rata realisasi per bulan berjalan (sampai bulan "
    f"{BULAN_LABEL.get(bulan_terakhir, '-')}) dikalikan 12 bulan. Ini estimasi sederhana, "
    "bukan angka resmi."
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
    return f"""
Data satker:
- Kementerian/Lembaga: {nmdept} (kode {kddept})
- Satker: {nmsatker} (kode {kdsatker})
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
