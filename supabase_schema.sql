-- Jalankan di Supabase SQL Editor jika ingin menyimpan data di Supabase
-- (bukan wajib -- app.py secara default membaca data/pagu_realisasi.csv)

create table if not exists pagu_realisasi (
    id bigint generated always as identity primary key,
    tahun int not null,
    kddept int not null,
    nmdept text not null,
    kdsatker int not null,
    nmsatker text not null,
    jenis_belanja int not null,
    label_jenis_belanja text not null,
    pagu bigint not null,
    jan bigint default 0,
    feb bigint default 0,
    mar bigint default 0,
    apr bigint default 0,
    mei bigint default 0,
    jun bigint default 0,
    jul bigint default 0,
    ags bigint default 0,
    sep bigint default 0,
    okt bigint default 0,
    nov bigint default 0,
    des bigint default 0,
    realisasi bigint not null,
    sisa_pagu bigint not null,
    blokir bigint default 0
);

create index if not exists idx_pagu_realisasi_dept on pagu_realisasi (tahun, kddept);
create index if not exists idx_pagu_realisasi_satker on pagu_realisasi (tahun, kdsatker);
