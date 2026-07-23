"""
build_from_raw_csv.py
----------------------
Menggabungkan 6 file CSV mentah (pagu_real21.csv .. pagu_real26.csv) menjadi satu
data/pagu_realisasi.csv yang dipakai app.py.

Kenapa perlu skrip khusus (bukan cuma pd.read_csv biasa):
- File 2022-2025: setiap baris dibungkus SATU kutip ganda besar di seluruh baris
  (bukan hanya per-kolom yang butuh), jadi harus di-"unwrap" dulu.
- File 2021: mengalami korupsi tambahan -- ada baris baru (newline) liar yang memecah
  satu baris logis jadi 2-3 baris fisik. Skrip ini merekonstruksi baris yang terpecah
  berdasarkan pola "baris baru dimulai dengan kode kementerian (angka)".
- File 2026: sudah CSV standar (quote hanya di kolom yang perlu), dan kolom bulan
  Agustus-Desember belum ada (data baru sampai Juli) -> diisi 0.

Jalankan:
    python build_from_raw_csv.py
(path file sumber & tahun sudah di-hardcode sesuai nama file yang diberikan)
"""

import csv
import io
import re
import sys

import pandas as pd

BULAN_KOLOM = ["jan", "feb", "mar", "apr", "mei", "jun",
               "jul", "ags", "sep", "okt", "nov", "des"]
BULAN_OUT = ["JAN", "FEB", "MAR", "APR", "MEI", "JUN",
             "JUL", "AGS", "SEP", "OKT", "NOV", "DES"]

LABEL_JENIS_BELANJA = {
    51: "Belanja Pegawai", 52: "Belanja Barang", 53: "Belanja Modal",
    54: "Belanja Pembayaran Bunga Utang", 55: "Belanja Subsidi",
    56: "Belanja Hibah", 57: "Belanja Bantuan Sosial", 58: "Belanja Lain-lain",
    61: "Transfer Daerah - Dana Bagi Hasil", 62: "Transfer Daerah - Dana Alokasi Umum",
    63: "Transfer Daerah - Dana Alokasi Khusus", 64: "Transfer Daerah - Insentif Fiskal",
    65: "Transfer Daerah - Dana BOK", 66: "Transfer Daerah - Dana Desa",
}

FILES = [
    ("/mnt/user-data/uploads/pagu_real21.csv", 2021),
    ("/mnt/user-data/uploads/pagu_real22.csv", 2022),
    ("/mnt/user-data/uploads/pagu_real23.csv", 2023),
    ("/mnt/user-data/uploads/pagu_real24.csv", 2024),
    ("/mnt/user-data/uploads/pagu_real25.csv", 2025),
    ("/mnt/user-data/uploads/pagu_real26.csv", 2026),
]


def parse_wrapped_year(path: str, year: int):
    """Untuk file yang tiap barisnya dibungkus satu kutip besar (2022-2025)."""
    with open(path, encoding="utf-8", newline="") as f:
        header = f.readline().strip().split(",")
        ncols = len(header)
        rows, bad = [], 0
        for raw in f:
            raw = raw.rstrip("\r\n")
            if not raw:
                continue
            if raw.startswith('"') and raw.endswith('"'):
                inner = raw[1:-1].replace('""', '"')
            else:
                inner = raw
            try:
                row = next(csv.reader(io.StringIO(inner)))
            except Exception:
                bad += 1
                continue
            if len(row) == ncols:
                rows.append(row)
            else:
                bad += 1
    print(f"  {year}: {len(rows):,} baris OK, {bad:,} baris dilewati (gagal parse)")
    return pd.DataFrame(rows, columns=header)


def parse_corrupt_2021(path: str, year: int = 2021):
    """Untuk file 2021: rekonstruksi baris yang terpecah newline, lalu unwrap seperti di atas."""
    with open(path, encoding="utf-8") as f:
        lines = f.readlines()

    header = lines[0].strip().split(",")
    ncols = len(header)

    start_pat = re.compile(r"^\d{3,4},[A-Za-z]")
    records, current = [], []
    for line in lines[1:]:
        if start_pat.match(line) and current:
            records.append(current)
            current = [line]
        else:
            current.append(line)
    if current:
        records.append(current)

    rows, bad = [], 0
    for rec in records:
        joined = "".join(l.rstrip("\n") for l in rec)
        candidate = '"' + joined
        inner = candidate[1:-1] if candidate.endswith('"') else candidate[1:]
        inner = inner.replace('""', '"')
        try:
            row = next(csv.reader(io.StringIO(inner)))
        except Exception:
            bad += 1
            continue
        if len(row) == ncols:
            rows.append(row)
        else:
            bad += 1
    print(f"  {year}: {len(rows):,} baris berhasil direkonstruksi, {bad:,} baris dilewati "
          f"(file sumber 2021 mengalami korupsi format, lihat catatan)")
    return pd.DataFrame(rows, columns=header)


def parse_standard_year(path: str, year: int):
    """Untuk file yang sudah CSV standar (2026)."""
    df = pd.read_csv(path)
    print(f"  {year}: {len(df):,} baris (format CSV standar, tidak ada masalah parsing)")
    return df


def normalize(df: pd.DataFrame, year: int) -> pd.DataFrame:
    df = df.copy()
    df.columns = [c.strip() for c in df.columns]

    out = pd.DataFrame()
    out["KDDEPT"] = pd.to_numeric(df["kementerian_kode"], errors="coerce")
    out["TAHUN"] = year
    out["NMDEPT"] = df["kementerian_uraian"].astype(str).str.strip()
    out["KDSATKER"] = pd.to_numeric(df["satker_kode"], errors="coerce")
    out["NMSATKER"] = df["satker_uraian"].astype(str).str.strip()

    akun = pd.to_numeric(df["akun_kode"], errors="coerce")
    out["JENIS BELANJA"] = (akun // 10000).astype("Int64")
    out["LABEL_JENIS_BELANJA"] = out["JENIS BELANJA"].map(LABEL_JENIS_BELANJA)
    out["LABEL_JENIS_BELANJA"] = out["LABEL_JENIS_BELANJA"].fillna(
        "Lainnya (" + out["JENIS BELANJA"].astype(str) + ")"
    )

    out["PAGU"] = pd.to_numeric(df["pagu_dipa"], errors="coerce").fillna(0)
    for src, dst in zip(BULAN_KOLOM, BULAN_OUT):
        if src in df.columns:
            out[dst] = pd.to_numeric(df[src], errors="coerce").fillna(0)
        else:
            out[dst] = 0  # kolom bulan yang belum ada di tahun berjalan (mis. 2026)

    out["BLOKIR"] = pd.to_numeric(df.get("blokir", 0), errors="coerce").fillna(0)

    # Buang baris yang gagal konversi kode dasar (data rusak/tidak lengkap)
    before = len(out)
    out = out.dropna(subset=["KDDEPT", "KDSATKER", "JENIS BELANJA"])
    dropped = before - len(out)
    if dropped:
        print(f"  {year}: {dropped:,} baris tambahan dibuang (kode dept/satker/akun tidak valid)")

    out["KDDEPT"] = out["KDDEPT"].astype(int)
    out["KDSATKER"] = out["KDSATKER"].astype(int)
    out["JENIS BELANJA"] = out["JENIS BELANJA"].astype(int)

    out["REALISASI"] = out[BULAN_OUT].sum(axis=1)
    out["SISA PAGU"] = out["PAGU"] - out["REALISASI"]

    return out


def main():
    print("Memproses file per tahun...")
    frames = []
    for path, year in FILES:
        if year == 2026:
            raw = parse_standard_year(path, year)
        else:
            raw = parse_wrapped_year(path, year)
        frames.append(normalize(raw, year))

    combined = pd.concat(frames, ignore_index=True)
    combined.to_csv("data/pagu_realisasi.csv.gz", index=False, compression="gzip")
    print(f"\nSelesai. Total {len(combined):,} baris, tahun {sorted(combined['TAHUN'].unique())}, "
          f"disimpan ke data/pagu_realisasi.csv.gz")


if __name__ == "__main__":
    main()
