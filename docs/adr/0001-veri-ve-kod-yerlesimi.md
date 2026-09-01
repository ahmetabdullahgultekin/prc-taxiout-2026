# ADR-0001: Kod OneDrive'da, veri D: surucusunde

Tarih: 2026-09-01 · Durum: kabul edildi

## Baglam

Gelistirme makinesi: 16 GB RAM, C: 475 GB'in 30 GB'i bos (%6.4), D: 231 GB'in 39 GB'i bos.
C: DRAM-siz bir Toshiba BG4 SSD; %90 doluluk asildiginda yazma hizi ~28 MB/s'ye cokuyor
(daha once olculdu). Ayrica repo OneDrive klasorunde — `.venv/` ve parquet dosyalari
surekli senkronizasyon trafigi yaratir.

## Karar

- **Kod, dokumanlar, testler:** `C:/Users/ahabg/OneDrive/Belgeler/GitHub/prc-taxiout-2026`
  (OneDrive senkronu kaynak kod icin yedek islevi gorur, digger projelerle tutarli).
- **Veri, ozellikler, modeller, sanal ortam:** `D:/prc-taxiout-2026/`
  (`00_raw`, `01_interim`, `02_features`, `03_models`, `04_submissions`, `.venv`).
- Yol, `TAXIOUT_DATA_DIR` ortam degiskeni veya `--data-dir` bayragi ile degistirilebilir.
  Kodda **mutlak yol yazilmaz** — 2025 jurisi hardcoded Windows yollarini acikca elestirdi.

## Sonuclar

- `.gitignore` `data/` ve `*.parquet` iceriyor; ham yarisma verisi asla commit edilmez
  (form sarti: veri kamuya acilana kadar yarisma disinda kullanilamaz, F11).
- Sanal ortam repo disinda oldugu icin calistirma komutlari yorumlayici yolunu acikca verir.
