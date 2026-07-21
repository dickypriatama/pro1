# Dashboard Pagu & Realisasi Satker

Dashboard interaktif untuk menampilkan pagu, realisasi, komposisi belanja, dan proyeksi
realisasi akhir tahun per Kementerian/Lembaga dan Satuan Kerja (Satker), lengkap dengan
narasi otomatis dan chat box berbasis AI (Groq).

## Struktur proyek

```
pagu-app/
├── app.py                      # Aplikasi Streamlit utama
├── data_prep.py                # Ubah file xlsx sumber -> data/pagu_realisasi.csv
├── data/pagu_realisasi.csv     # Data yang dipakai app (sudah dibuat dari file kamu)
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
- **Supabase** — *opsional*. Secara default data dibaca langsung dari `data/pagu_realisasi.csv`
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

## Memperbarui data

Kalau ada file pagu-realisasi baru (misalnya update bulanan):

```bash
python data_prep.py path/ke/file_baru.xlsx
git add data/pagu_realisasi.csv
git commit -m "Update data bulan X"
git push
```

Atau, jika pakai Supabase, cukup jalankan ulang `supabase_upload.py` tanpa perlu push kode.

## Catatan tentang proyeksi akhir tahun

Proyeksi dihitung dengan metode run-rate sederhana: rata-rata realisasi per bulan berjalan
(dari bulan Januari sampai bulan terakhir yang datanya terisi) dikalikan 12. Ini estimasi
kasar untuk membantu membaca tren, bukan angka resmi/proyeksi fiskal formal.
