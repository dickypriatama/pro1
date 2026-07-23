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
    return load_data_from_csv("data/pagu_realisasi.csv.gz")


KOLOM_TEKS_CARI = [
    "NMDEPT", "NMSATKER", "PROVINSI", "KABKOTA", "FUNGSI", "SUBFUNGSI",
    "PROGRAM", "KEGIATAN", "OUTPUT", "AKUN",
]


@st.cache_data(show_spinner="Menyiapkan data...")
def siapkan_data(df_mentah: pd.DataFrame) -> pd.DataFrame:
    d = df_mentah.copy()
    # REALISASI & SISA PAGU dihitung ulang dari total kolom bulanan (JAN..DES).
    # Ini supaya semua angka di dashboard konsisten dengan rincian bulanannya -- pada
    # sebagian data sumber, kolom REALISASI bawaan bisa tidak sinkron dengan JAN..DES-nya.
    d["REALISASI"] = d[BULAN_KOLOM].sum(axis=1)
    d["SISA PAGU"] = d["PAGU"] - d["REALISASI"]

    # Kolom teks gabungan (lowercase) untuk pencarian tematik AI (mis. "ketahanan pangan",
    # "kebakaran hutan") -- dipakai fitur pencarian di chat box.
    kolom_ada = [c for c in KOLOM_TEKS_CARI if c in d.columns]
    if kolom_ada:
        d["_TEKS_CARI"] = (
            d[kolom_ada].fillna("").astype(str).agg(" ".join, axis=1).str.lower()
        )
    else:
        d["_TEKS_CARI"] = ""
    return d


df = siapkan_data(load_data())


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

jenis_belanja = (
    df_satker.groupby("LABEL_JENIS_BELANJA")["REALISASI"]
    .sum()
    .sort_values(ascending=False)
    .reset_index()
)


# --------------------------------------------------------------------------
# Proyeksi: rerata tertimbang tingkat realisasi 5 tahun sebelumnya x pagu tahun berjalan
#
#   proyeksi_bulan_m = pagu_tahun_ini * [ Σ bobot_i * (realisasi_bulan_m_tahun(y-i) / pagu_tahun(y-i)) ] / Σ bobot_i
#
# bobot: y-1=50%, y-2=25%, y-3=12,5%, y-4=6,25%, y-5=6,25%. Tahun yang datanya tidak ada di
# sumber (mis. satker belum ada / pagu=0) dilewati, dan bobotnya dinormalisasi ulang di antara
# tahun-tahun yang tersedia.
# --------------------------------------------------------------------------

BOBOT_TAHUN = {1: 0.50, 2: 0.25, 3: 0.125, 4: 0.0625, 5: 0.0625}


def _filter_entitas(thn: int) -> pd.DataFrame:
    d = df[df["TAHUN"] == thn]
    if kddept is not None:
        d = d[d["KDDEPT"] == kddept]
    if kdsatker is not None:
        d = d[d["KDSATKER"] == kdsatker]
    return d


def hitung_proyeksi_agregat(tahun_y: int, pagu_y: float):
    """Proyeksi 12 bulan (rupiah) untuk seluruh satker/entitas terpilih. Return (array atau None, daftar tahun yang dipakai)."""
    total_rate = np.zeros(12)
    total_bobot = 0.0
    tahun_dipakai = []
    for i in range(1, 6):
        d_prev = _filter_entitas(tahun_y - i)
        pagu_prev = d_prev["PAGU"].sum() if not d_prev.empty else 0
        if pagu_prev <= 0:
            continue
        monthly_prev = d_prev[BULAN_KOLOM].sum().values.astype(float)
        total_rate += BOBOT_TAHUN[i] * (monthly_prev / pagu_prev)
        total_bobot += BOBOT_TAHUN[i]
        tahun_dipakai.append(tahun_y - i)
    if total_bobot == 0:
        return None, tahun_dipakai
    return (total_rate / total_bobot) * pagu_y, tahun_dipakai


def hitung_proyeksi_per_jenis(tahun_y: int, pagu_per_jenis_now: pd.Series):
    """Proyeksi 12 bulan (rupiah) per jenis belanja. Return dict label -> array(12) atau None."""
    hasil = {}
    tahun_dipakai_semua = set()
    for label, pagu_now in pagu_per_jenis_now.items():
        total_rate = np.zeros(12)
        total_bobot = 0.0
        for i in range(1, 6):
            d_prev = _filter_entitas(tahun_y - i)
            d_prev = d_prev[d_prev["LABEL_JENIS_BELANJA"] == label]
            pagu_prev = d_prev["PAGU"].sum() if not d_prev.empty else 0
            if pagu_prev <= 0:
                continue
            monthly_prev = d_prev[BULAN_KOLOM].sum().values.astype(float)
            total_rate += BOBOT_TAHUN[i] * (monthly_prev / pagu_prev)
            total_bobot += BOBOT_TAHUN[i]
            tahun_dipakai_semua.add(tahun_y - i)
        hasil[label] = (total_rate / total_bobot) * pagu_now if total_bobot > 0 else None
    return hasil, sorted(tahun_dipakai_semua, reverse=True)


proyeksi_agregat_bulanan, tahun_dipakai = hitung_proyeksi_agregat(tahun, pagu_total)

if proyeksi_agregat_bulanan is None:
    # Tidak ada histori sama sekali (mis. tahun pertama dalam data) -> fallback rata-rata bulan berjalan
    rerata_bulanan = (kumulatif.iloc[bulan_terakhir - 1] / bulan_terakhir) if bulan_terakhir else 0
    proyeksi_akhir_tahun = rerata_bulanan * 12
    metode_proyeksi = "fallback"
else:
    proyeksi_akhir_tahun = realisasi_total + sum(
        proyeksi_agregat_bulanan[m] for m in range(bulan_terakhir, 12)
    )
    metode_proyeksi = "historis"

persen_proyeksi = (proyeksi_akhir_tahun / pagu_total * 100) if pagu_total else 0


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
        if proyeksi_agregat_bulanan is not None:
            proyeksi.append(proyeksi_agregat_bulanan[b - 1])
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

if metode_proyeksi == "historis":
    daftar_tahun_ket = ", ".join(str(t) for t in tahun_dipakai)
    st.caption(
        "Grafik ini menampilkan realisasi tiap bulan (bukan kumulatif) supaya terlihat bulan mana "
        "yang realisasinya naik/turun. Bulan setelah "
        f"{BULAN_LABEL.get(bulan_terakhir, '-')} adalah proyeksi yang dihitung dari rerata tertimbang "
        "tingkat realisasi tahun-tahun sebelumnya (bobot 50%-25%-12,5%-6,25%-6,25% untuk tahun "
        f"y-1 s.d. y-5) dikalikan pagu tahun {tahun}. Tahun historis yang tersedia & dipakai: "
        f"{daftar_tahun_ket}."
    )
else:
    st.caption(
        "Grafik ini menampilkan realisasi tiap bulan (bukan kumulatif) supaya terlihat bulan mana "
        "yang realisasinya naik/turun. Bulan setelah "
        f"{BULAN_LABEL.get(bulan_terakhir, '-')} adalah proyeksi. Belum ada data historis (tahun "
        f"sebelum {tahun}) untuk entitas ini, sehingga proyeksi memakai metode cadangan: rata-rata "
        "realisasi per bulan pada tahun berjalan dikalikan 12 bulan."
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

proyeksi_per_jenis, _ = hitung_proyeksi_per_jenis(tahun, pagu_per_jenis.reindex(urutan_kode))

mask_proyeksi = pd.DataFrame(False, index=tabel.index, columns=BULAN_KOLOM)
if bulan_terakhir < 12:
    for jb in tabel.index:
        proyeksi_jb = proyeksi_per_jenis.get(jb)
        if proyeksi_jb is None:
            # tidak ada histori utk jenis belanja ini -> fallback rata-rata realisasi tahun berjalan
            actual_sum = tabel.loc[jb, BULAN_KOLOM[:bulan_terakhir]].sum() if bulan_terakhir else 0
            rerata_jb = actual_sum / bulan_terakhir if bulan_terakhir else 0
            for m in range(bulan_terakhir, 12):
                tabel.loc[jb, BULAN_KOLOM[m]] = rerata_jb
        else:
            for m in range(bulan_terakhir, 12):
                tabel.loc[jb, BULAN_KOLOM[m]] = proyeksi_jb[m]
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
    "🟨 Sel berwarna kuning = angka proyeksi (belum realisasi aktual), dihitung dari rerata "
    "tertimbang tingkat realisasi jenis belanja ini pada tahun-tahun sebelumnya (lihat penjelasan "
    "di atas grafik tren) dikalikan pagu jenis belanja tahun berjalan. Jika suatu jenis belanja "
    "belum punya histori, dipakai rata-rata realisasi tahun berjalan sebagai cadangan. Kolom PAGU "
    f"dan kolom \"{TOTAL_COL}\" tidak ditandai kuning karena berupa gabungan/acuan, bukan proyeksi murni."
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


# --------------------------------------------------------------------------
# Pencarian tematik lintas satker/kementerian/provinsi -- dipakai AI di chat box
# untuk menjawab pertanyaan seperti "berapa pagu ketahanan pangan di Riau?" atau
# "penanganan karhutla ada di satker mana saja?".
# --------------------------------------------------------------------------

def cari_anggaran(kata_kunci: list, provinsi: str = None, tahun_cari: int = None) -> dict:
    d = df
    d = d[d["TAHUN"] == (tahun_cari or tahun)]

    if provinsi:
        if "PROVINSI" in d.columns:
            d = d[d["PROVINSI"].str.contains(provinsi, case=False, na=False)]
        else:
            return {"error": "Kolom provinsi tidak tersedia di data ini."}

    if kata_kunci:
        mask = pd.Series(False, index=d.index)
        for kw in kata_kunci:
            mask = mask | d["_TEKS_CARI"].str.contains(str(kw).lower(), na=False)
        d = d[mask]

    if d.empty:
        return {
            "ditemukan": False,
            "pesan": (
                "Tidak ada baris data yang cocok dengan kata kunci/filter ini. Kemungkinan "
                "temanya tidak tercatat secara eksplisit di nama program/kegiatan/output pada "
                "level detail yang tersedia di data ini."
            ),
        }

    rincian = (
        d.groupby(["KDDEPT", "NMDEPT", "KDSATKER", "NMSATKER"])
        .agg(PAGU=("PAGU", "sum"), REALISASI=("REALISASI", "sum"))
        .reset_index()
        .sort_values("PAGU", ascending=False)
        .head(30)
    )

    return {
        "ditemukan": True,
        "tahun": int(tahun_cari or tahun),
        "jumlah_baris_cocok": int(len(d)),
        "jumlah_satker_ditemukan": int(rincian.shape[0]),
        "total_pagu": float(d["PAGU"].sum()),
        "total_realisasi": float(d["REALISASI"].sum()),
        "rincian_per_satker_top30": rincian.to_dict(orient="records"),
        "catatan": (
            "rincian_per_satker_top30 diurutkan dari pagu terbesar, dibatasi 30 baris teratas. "
            "total_pagu & total_realisasi sudah menjumlahkan SEMUA satker yang cocok, tidak "
            "hanya yang ditampilkan di rincian."
        ),
    }


TOOLS_GROQ = [
    {
        "type": "function",
        "function": {
            "name": "cari_anggaran",
            "description": (
                "Mencari & menjumlahkan pagu/realisasi anggaran di SELURUH data (semua "
                "kementerian & satker, bukan cuma yang sedang dipilih di dashboard), "
                "berdasarkan kata kunci tema/program/kegiatan/output, dan opsional filter "
                "provinsi atau tahun. WAJIB dipakai untuk pertanyaan yang menyebutkan tema "
                "(mis. 'ketahanan pangan', 'kebakaran hutan'), lokasi/provinsi tertentu, atau "
                "kementerian/satker yang BUKAN yang sedang aktif di dashboard."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "kata_kunci": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            "Daftar kata kunci (boleh lebih dari satu sinonim) untuk dicari di "
                            "nama kementerian/satker/provinsi/fungsi/program/kegiatan/output/akun. "
                            "Contoh: ['ketahanan pangan'] atau ['kebakaran hutan', 'karhutla']."
                        ),
                    },
                    "provinsi": {
                        "type": "string",
                        "description": "Nama provinsi untuk filter lokasi. Kosongkan jika tidak spesifik ke satu provinsi.",
                    },
                    "tahun_cari": {
                        "type": "integer",
                        "description": "Tahun anggaran yang dicari. Kosongkan untuk memakai tahun yang sedang dipilih di dashboard.",
                    },
                },
                "required": ["kata_kunci"],
            },
        },
    }
]


def jalankan_tool_call(nama_fungsi: str, args: dict) -> str:
    import json
    if nama_fungsi == "cari_anggaran":
        hasil = cari_anggaran(
            kata_kunci=args.get("kata_kunci", []),
            provinsi=args.get("provinsi"),
            tahun_cari=args.get("tahun_cari"),
        )
    else:
        hasil = {"error": f"Fungsi tidak dikenal: {nama_fungsi}"}
    return json.dumps(hasil, ensure_ascii=False)


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
st.caption(
    "Bisa tanya soal satker yang sedang dipilih, atau tema/lokasi lain -- misalnya "
    "\"berapa pagu ketahanan pangan di Riau?\" atau \"anggaran penanganan karhutla ada di "
    "satker apa saja?\". AI otomatis mencari di seluruh data kalau perlu."
)

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

for msg in st.session_state.chat_history:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

prompt = st.chat_input("Tulis pertanyaan tentang pagu/realisasi satker ini, atau tanya tema/provinsi lain...")

if prompt:
    st.session_state.chat_history.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.write(prompt)

    if client is None:
        jawaban = "Fitur chat AI belum aktif karena GROQ_API_KEY belum di-set. Lihat README.md."
    else:
        with st.spinner("AI sedang menjawab..."):
            system_msg = {
                "role": "system",
                "content": (
                    "Kamu adalah asisten analisis anggaran pemerintah Indonesia. Untuk pertanyaan "
                    "tentang satker/kementerian yang SEDANG dipilih di dashboard, jawab langsung "
                    "memakai data di bawah ini. Untuk pertanyaan tentang TEMA (mis. 'ketahanan "
                    "pangan', 'kebakaran hutan'), PROVINSI tertentu, atau kementerian/satker LAIN "
                    "di luar yang sedang aktif, WAJIB panggil fungsi cari_anggaran untuk mencari di "
                    "seluruh data -- jangan mengarang angka. Kalau hasil pencarian menyatakan tidak "
                    "ditemukan, katakan dengan jujur bahwa datanya tidak ditemukan pada level detail "
                    "yang tersedia, jangan mengarang jawaban.\n\n" + ringkasan_data_untuk_ai()
                ),
            }
            messages = [system_msg] + st.session_state.chat_history

            resp = client.chat.completions.create(
                model=GROQ_MODEL, messages=messages, tools=TOOLS_GROQ, tool_choice="auto",
            )
            msg = resp.choices[0].message

            if msg.tool_calls:
                import json as _json
                messages.append({
                    "role": "assistant",
                    "content": msg.content or "",
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                        }
                        for tc in msg.tool_calls
                    ],
                })
                for tc in msg.tool_calls:
                    try:
                        args = _json.loads(tc.function.arguments)
                    except Exception:
                        args = {}
                    hasil_tool = jalankan_tool_call(tc.function.name, args)
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": hasil_tool,
                    })
                resp2 = client.chat.completions.create(model=GROQ_MODEL, messages=messages)
                jawaban = resp2.choices[0].message.content
            else:
                jawaban = msg.content

    st.session_state.chat_history.append({"role": "assistant", "content": jawaban})
    with st.chat_message("assistant"):
        st.write(jawaban)
