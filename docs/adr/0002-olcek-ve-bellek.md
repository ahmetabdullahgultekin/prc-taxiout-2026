# ADR-0002: Bellekte calisan boru hatti yeterli, out-of-core gerekmiyor

Tarih: 2026-09-01 · Durum: kabul edildi

## Baglam

Makine 16 GB RAM (kullanilabilir 15,9). Yarisma verisi 4.167.797 hareket, ~277 MB
parquet. Tasarima baslarken belirsiz olan soru: oznitelik uretimi bellekte yapilabilir
mi, yoksa havalimani bazinda parcalayip diske yazmak mi gerekiyor?

Belirsizligi tahminle degil olcumle kapattik: `tests/make_fixture.py --per-day 12400`
ile gercek boyutta (4.166.400 hareket, 252 MB parquet) sentetik veri uretilip boru
hatti uctan uca calistirildi.

## Olcum (2026-09-01)

| Asama | Sure | Tepe RSS |
|---|---|---|
| veri yukleme (4,17M hareket) | 1 sn | 1,75 GB |
| oznitelik uretimi (2,08M kalkis x 114 kolon) | 28 sn | 3,91 GB |
| bolme + ATXOT referansi | 2 sn | **5,15 GB** |
| matris (1,74M x 95 float32 = 0,61 GB) | 3 sn | 4,68 GB |
| egitim (LightGBM, 200 tur) | 63 sn | 4,16 GB |
| **uctan uca dogrulama kosusu** | **96 sn** | **5,15 GB** |
| **gonderim yolu** (egitim + siralama ozniteligi ayni anda) | **171 sn** | **7,06 GB** |

## Karar

Boru hatti **tamamen bellekte** calisir. Havalimani bazinda parcalama, diske ara yazma
ve out-of-core kurgusu **yapilmayacak**.

## Gerekce

En yuksek bellek noktasi olan gonderim yolunda bile 7,06 GB / 15,9 GB kullaniliyor,
yani iki kattan fazla pay var. Parcalama kodu belirgin sekilde karmasiklastirir ve
2025 jurisi bir takimi gereksiz yapilandirma nedeniyle acikca elestirdi.

## Sonuclar

- Tam ablation (13 yapilandirma x 1500 tur) yaklasik **1,7 saat**; 5 tohumla ~8,5 saat.
  Gece kosusu olarak planlanabilir, gun ici iterasyon icin tur sayisi dusuk tutulur.
- `float32` ve `max_bin=127` secimleri korunur; bu paylar onlarla olculdu.
- Olcek testi tekrarlanabilir: `tests/make_fixture.py --per-day 12400`.
- **Uyari:** olcum sentetik veriyle yapildi. Gercek verinin kategorik kardinalitesi
  (ozellikle `STAND_mvt` ve `AIRCRAFT_OPERATOR_flt`) daha yuksek olabilir; veri gelince
  ilk tam kosuda bellek yeniden olculecek.
