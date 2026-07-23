# Dashboard Pagu & Realisasi Satker

Dashboard interaktif untuk menampilkan pagu, realisasi, komposisi belanja, dan proyeksi
realisasi akhir tahun per Kementerian/Lembaga dan Satuan Kerja (Satker), lengkap dengan
narasi otomatis dan chat box berbasis AI (Groq).

## Struktur proyek

```
pagu-app/
├── app.py                      # Aplikasi Streamlit utama
├── data_prep.py                # Ubah file xlsx sumber -> data/pagu_realisasi.csv.gz
├── data/pagu_realisasi.csv.gz  # Data yang dipakai app (sudah dibuat dari file kamu)
├── requirements.txt
├── supabase_schema.sql         # (opsional) skema tabel jika mau pakai Supabase
├── supabase_upload.py          # (opsional) unggah CSV ke Supabase
└── .streamlit/
    └── secrets.toml.example    # contoh isi secrets, salin jadi secrets.toml
```

## Peran masing-masing komponen

- **Streamlit** — merender seluruh tampilan (dropdown, grafik, chat box).
- **Groq** — model AI di balik "Narasi Otomatis" dan kotak chat bebas. Cepat dan gratis
  untuk pemakaian ringan.
- **GitHub** — menyimpan kode ini, sekaligus jadi sumber deploy otomatis ke Streamlit Cloud.
- **Supabase** — *opsional*. Secara default data dibaca langsung dari `data/pagu_realisasi.csv.gz`
  yang dibundel di repo (paling simpel, cukup untuk kebanyakan kasus). Pakai Supabase kalau kamu
  mau: (a) data terpusat yang bisa diperbarui tanpa redeploy kode, atau (b) beberapa
  aplikasi/tim mengakses data yang sama.

## 1. Jalankan di komputer sendiri

```bash
cd pagu-app
pip install -r requirements.txt
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# lalu isi GROQ_API_KEY di .streamlit/secrets.toml
streamlit run app.py
```

Buka http://localhost:8501

## 2. Dapatkan API key Groq (gratis)

1. Daftar di https://console.groq.com
2. Buat API key baru
3. Tempel di `.streamlit/secrets.toml` sebagai `GROQ_API_KEY`

Model default yang dipakai: `openai/gpt-oss-120b` (rekomendasi Groq saat ini untuk kualitas
terbaik). Cek daftar model terbaru & yang sudah deprecated di
https://console.groq.com/docs/models sebelum deploy — model bisa berubah sewaktu-waktu.
Kamu bisa ganti model lewat environment variable `GROQ_MODEL` kalau perlu.

## 3. Push ke GitHub

```bash
cd pagu-app
git init
git add .
echo ".streamlit/secrets.toml" >> .gitignore
git add .gitignore
git commit -m "Dashboard pagu realisasi satker"
git branch -M main
git remote add origin https://github.com/<username>/<nama-repo>.git
git push -u origin main
```

**Penting:** jangan pernah commit `.streamlit/secrets.toml` yang sudah terisi — file itu
sudah dimasukkan ke `.gitignore` di atas.

## 4. Deploy ke Streamlit Community Cloud

1. Buka https://streamlit.io/cloud, login pakai akun GitHub
2. Klik "New app", pilih repo dan branch di atas, file utama `app.py`
3. Di bagian "Advanced settings" → "Secrets", tempel isi `.streamlit/secrets.toml`
   (yang sudah terisi API key asli)
4. Klik Deploy

Setiap kali kamu `git push` update kode, Streamlit Cloud otomatis rebuild aplikasinya.

## 5. (Opsional) Pindah sumber data ke Supabase

Kalau data pagu/realisasi kamu akan sering di-update dan kamu tidak mau redeploy kode
setiap kali update data:

1. Buat project di https://supabase.com
2. Buka SQL Editor, jalankan isi `supabase_schema.sql`
3. Set env var lalu jalankan uploader:
   ```bash
   export SUPABASE_URL=https://xxxx.supabase.co
   export SUPABASE_KEY=<service_role_key>
   python supabase_upload.py
   ```
4. Di `secrets.toml` (lokal & Streamlit Cloud), set:
   ```toml
   USE_SUPABASE = "true"
   SUPABASE_URL = "https://xxxx.supabase.co"
   SUPABASE_KEY = "<anon_key>"   # untuk app, cukup pakai anon/public key (read-only)
   ```

Setelah itu, `app.py` otomatis membaca data dari Supabase, bukan dari CSV lokal.

## Fitur pencarian tematik di chat AI

Chat box sekarang bisa menjawab pertanyaan yang **tidak terbatas pada satker yang sedang
dipilih di dropdown**, misalnya:
- "Berapa pagu dan realisasi anggaran ketahanan pangan di Riau?"
- "Pagu anggaran penanganan kebakaran hutan ada di satker apa saja dan berapa nilainya?"

AI akan otomatis mencari di seluruh data (nama kementerian/satker/provinsi/fungsi/
program/kegiatan/output/akun) ketika pertanyaan menyebutkan tema atau lokasi tertentu.
Kalau temanya tidak tercatat secara eksplisit pada level detail yang tersedia di data
(mis. sub-kegiatan yang sangat spesifik), AI akan bilang jujur "tidak ditemukan" alih-alih
mengarang jawaban.

**Catatan:** akurasi pencarian tematik bergantung pada seberapa eksplisit nama program/
kegiatan/output mengandung kata kunci tersebut. Data ini hanya sampai level "Output"
(bukan Rincian Output/RO yang lebih detail), jadi kegiatan yang sangat spesifik kadang
tidak ketemu meskipun anggarannya ada.

## Ukuran file data

Data mentah (dengan kolom deskriptif untuk pencarian tematik) cukup besar dalam bentuk CSV
biasa (~52 MB), jadi disimpan dalam bentuk **terkompresi gzip**: `data/pagu_realisasi.csv.gz`
(~4,7 MB). Ini otomatis dibaca oleh `app.py` (pandas mengenali `.gz` secara otomatis) --
tidak perlu di-extract dulu. Ukuran ini jauh di bawah batas upload file GitHub (25 MB lewat
web/drag-drop, 100 MB lewat command line), jadi aman untuk di-upload lewat cara apa pun.

## Memperbarui data

Data saat ini mencakup tahun 2021-2026, digabungkan dari file mentah `pagu_real21-26.csv`
(format: pemisah titik-koma, angka gaya Indonesia, encoding latin-1) memakai skrip
`build_from_combined_csv.py`. Kalau nanti ada file gabungan baru dengan format yang sama:

```bash
# taruh file baru di lokasi yang sama lalu jalankan:
python build_from_combined_csv.py
git add data/pagu_realisasi.csv.gz
git commit -m "Update data pagu realisasi"
git push
```

Kalau ada file pagu-realisasi baru dalam format xlsx seperti awal (satu tahun per file):

```bash
python data_prep.py path/ke/file_baru.xlsx
git add data/pagu_realisasi.csv.gz
git commit -m "Update data bulan X"
git push
```

Atau, jika pakai Supabase, cukup jalankan ulang `supabase_upload.py` tanpa perlu push kode.

## Catatan tentang proyeksi akhir tahun

Proyeksi dihitung dengan metode run-rate sederhana: rata-rata realisasi per bulan berjalan
(dari bulan Januari sampai bulan terakhir yang datanya terisi) dikalikan 12. Ini estimasi
kasar untuk membantu membaca tren, bukan angka resmi/proyeksi fiskal formal.
