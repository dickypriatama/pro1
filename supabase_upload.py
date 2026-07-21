"""
supabase_upload.py
-------------------
Opsional: unggah data/pagu_realisasi.csv ke tabel Supabase (lihat supabase_schema.sql).
Baru jalankan ini kalau kamu memang ingin data disimpan/dibaca dari Supabase,
bukan dari file CSV yang dibundel di repo.

Pemakaian:
    export SUPABASE_URL=https://xxxx.supabase.co
    export SUPABASE_KEY=xxxxx   # gunakan service_role key (bukan anon key) untuk upload
    python supabase_upload.py
"""

import os
import sys

import pandas as pd
from supabase import create_client

BATCH_SIZE = 500


def main():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    table = os.environ.get("SUPABASE_TABLE", "pagu_realisasi")

    if not url or not key:
        print("Set dulu env var SUPABASE_URL dan SUPABASE_KEY.")
        sys.exit(1)

    df = pd.read_csv("data/pagu_realisasi.csv")
    df = df.rename(columns={
        "TAHUN": "tahun", "KDDEPT": "kddept", "NMDEPT": "nmdept",
        "KDSATKER": "kdsatker", "NMSATKER": "nmsatker",
        "JENIS BELANJA": "jenis_belanja", "LABEL_JENIS_BELANJA": "label_jenis_belanja",
        "PAGU": "pagu", "JAN": "jan", "FEB": "feb", "MAR": "mar", "APR": "apr",
        "MEI": "mei", "JUN": "jun", "JUL": "jul", "AGS": "ags", "SEP": "sep",
        "OKT": "okt", "NOV": "nov", "DES": "des",
        "REALISASI": "realisasi", "SISA PAGU": "sisa_pagu", "BLOKIR": "blokir",
    })

    client = create_client(url, key)
    records = df.to_dict(orient="records")

    for i in range(0, len(records), BATCH_SIZE):
        batch = records[i:i + BATCH_SIZE]
        client.table(table).insert(batch).execute()
        print(f"Terunggah {i + len(batch)}/{len(records)}")

    print("Selesai.")


if __name__ == "__main__":
    main()
