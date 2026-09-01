# Proje Talimatlari — PRC Data Challenge 2026 (taxi-out)

## Ne yapiyoruz

11 Avrupa havalimaninda **kalkis** hareketlerinin taxi-out suresini saniye cinsinden tahmin ediyoruz.
Metrik **RMSE**. Sıralama seti Ocak + Temmuz 2026. Son tarih **2026-10-11 23:59:59 CET**.

Hedef: ilk 3. Odul yalnizca RMSE ile alinmiyor — juri depoyu ve dokumantasyonu da degerlendiriyor
(bkz. `docs/facts.md` F14).

## Once oku

Herhangi bir modelleme kararindan once **`docs/facts.md`** ve **`docs/reference/atxot-notes.md`**
okunacak. Yarisma kurallari ve resmi metodoloji orada, kaynak ve tarihle birlikte.
Ezberden kural veya kolon adi soyleme — sicilde yoksa dogrula ve sicile ekle.

## Katı kurallar

1. **Mutlak yol yazma.** Veri yolu `TAXIOUT_DATA_DIR` ortam degiskeni veya `--data-dir`
   bayragindan gelir. 2025 jurisi hardcoded Windows yollarini acikca elestirdi.
2. **pandas kullanma, polars kullan.** 16 GB RAM'de 4.2M satir x cok kolon pandas'ta patlar.
   Toplu okuma icin `polars.scan_parquet` (lazy) veya duckdb. LightGBM sinirinda da
   pandas'a gecilmez: kategorikler tamsayi koda cevrilip float32 numpy verilir
   (`scripts/train_baseline.py:to_matrix`). Kategori seviye sozlugu egitimden dogrulamaya
   **tasinmali**, yoksa ayni kategori iki tarafta farkli koda duser ve model sessizce bozulur.
3. **Kayip fonksiyonu L2.** RMSE'nin optimal tahmincisi kosullu ortalamadir. Huber/MAE/quantile
   veya duzeltmesiz log-hedef sistematik sapma yaratir. Denenirse `docs/experiments.md`'ye
   negatif sonuc olarak yazilir.
4. **Rastgele K-fold yasak.** Dogrulama: 2025'ten Ocak ve Temmuz cikarilir, model kalan 10 ayla
   egitilir, o iki ayda **ayri ayri** raporlanir. Havalimani bazinda RMSE her zaman yazilir.
5. **Her deney `docs/experiments.md`'ye islenir** — ise yaramayanlar dahil.
6. **Ham yarisma verisi commit edilmez.** Form sarti: veri kamuya acilana kadar yarisma
   disinda kullanilamaz (F11).
7. **Dis veri kaynagi eklemeden once `docs/external_data.md` doldurulur.** Lisans yazilmadan
   kaynak kullanilmaz — odul uygunlugu sarti.
8. Depoda **saglayici/model adi gecmez** (commit, PR, dal adi, dosya adi, dokuman).

## Kod duzeni

```
src/taxiout/
  domain/       saf mantik, IO yok, ucuncu parti model kutuphanesi yok
  features/     saf donusumler: (LazyFrame) -> LazyFrame
  adapters/     IO: parquet, minio, metar, model kutuphaneleri
  application/  orkestrasyon: ozellik uret, egit, tahmin et, degerlendir
scripts/        tek seferlik / tanı araclari
```

Port/arayuz katmani **yok** — 6 haftalik tek amacli bir batch pipeline icin gereksiz soyutlama,
ve 2025 jurisi bir takimi "fazla yapilandirilmis olma noktasina varacak kadar" diye elestirdi.
Deger testedilebilir saf fonksiyonlarda ve tekrar uretilebilirlikte.

## Komutlar

```bash
PY=D:/prc-taxiout-2026/.venv/Scripts/python.exe

# veri tanisi (veri iner inmez ilk calistirilacak)
$PY scripts/probe_data.py

# dis veri: METAR (zaten indirildi, yeniden cekmek gerekmez)
$PY -m taxiout.adapters.metar_iem --start 2025-01-01 --end 2026-08-01     --out D:/prc-taxiout-2026/00_raw/metar.parquet

# uctan uca taban model + degerlendirme
$PY scripts/train_baseline.py --data-dir D:/prc-taxiout-2026
$PY scripts/train_baseline.py --data-dir D:/prc-taxiout-2026 --no-aobt3   # ablation

# gercek veri gelmeden borulari denemek icin sentetik fixture
$PY tests/make_fixture.py --out D:/prc-taxiout-2026/99_fixture/00_raw
$PY scripts/train_baseline.py --data-dir D:/prc-taxiout-2026/99_fixture --rounds 300

$PY -m pytest tests/unit -q
$PY -m ruff check src tests scripts
```

Takim adi **`vibrant-lollipop`**, gonderim bucket'i **`prc-2026-vibrant-lollipop`**,
dosya adi `vibrant-lollipop_vN.parquet`. `mc` istemcisi `~/bin/mc.exe` altinda kurulu.

**Ag tuzagi:** Cloudflare WARP acikken OSN'ye erisilemiyor. Veri indirmeden once
`warp-cli disconnect`.

`make` bu makinede kurulu degil — Makefile yok, dogrudan python cagriliyor.

## Ortam

Windows 11, 16 GB RAM, GTX 1650 (4 GB). **GPU kullanma** — bu veri boyutunda LightGBM
histogram CPU daha hizli, veri transferi kazanci yiyor. Bellek disiplini: float32,
kategorikler `pl.Categorical`, ozellik uretimi havalimani bazinda parcalanip diske yazilir.
