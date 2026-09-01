# PRC Data Challenge 2026 — Taxi-Out Time Prediction

11 buyuk Avrupa havalimaninda kalkis yapan ucaklarin **taxi-out suresini** (AOBT -> ATOT, saniye)
tahmin eden acik kaynakli cozum. EUROCONTROL Performance Review Commission (PRC) ve
OpenSky Network tarafindan duzenlenen 2026 veri yarismasi icin.

- Yarisma: <https://ansperformance.eu/study/data-challenge/dc2026/>
- Metrik: RMSE (saniye), Ocak + Temmuz 2026 kalkislari uzerinde
- Lisans: GNU GPLv3 (yarisma odul sartı)

## Durum

Veri erisimi icin takim olusturma basvurusu bekleniyor. Boru hatti veri gelmeden
kuruldu ve sentetik bir fixture uzerinde uctan uca dogrulandi.

## Yaklasim

Problem, EUROCONTROL'un kendi *additional taxi-out time* gostergesinin ayristirmasi
izlenerek kuruluyor:

    taxi-out = engelsiz referans + kuyruk + tikaniklik

**Referans bileseni** resmi metodolojinin sadik yeniden uygulamasidir: her
(havalimani, stand, kalkis pisti) kombosu icin P10, geçerlilik icin P10 altinda en az
10 ucus (`src/taxiout/domain/reference.py`). Model bu tabanin uzerindeki **artigi**
ogrenir.

**Kuyruk ve tikaniklik bilesenleri** hareket akisindan uretilir. Siralama setinde
kalkislarin yalnizca blok saati ve taxi suresi bosaltilmis; kalkis saati, pist, stand
ve varislarin tamami duruyor. Dolayisiyla bir kalkisin cevresindeki trafik tam olarak
gozlenebilir. Bu, **post-operasyon** kurgusunun dogal sonucudur (yarismanin belirtilen
amaci da odur), ve gercek zamanli bir modelde tahmin edilmek zorunda olan kuyruk
degiskenini burada olculebilir kilar.

Ayni kod iki model uretir:

| | cipa | kullanim |
|---|---|---|
| retrospektif | kalkis ani | yarisma gonderimi; post-ops KPI, eksik veri doldurma |
| nedensel | blok cozulme ani | A-CDM / TSAT / DMAN gibi gercek zamanli kararlar |

Ikisi ayni dogrulama kumesinde karsilastirilabilir; aradaki fark retrospektif
gozlenebilirligin bilgi degeridir.

## Dis veri

| Kaynak | Lisans | Ne icin |
|--------|--------|---------|
| [Iowa Environmental Mesonet ASOS/METAR](https://mesonet.agron.iastate.edu/) | kamu mali | sicaklik, gorus, ruzgar, yagis; de-icing vekili |
| [OurAirports](https://ourairports.com/data/) | kamu mali | koordinatlar (kalkis kerterizi), pist sayilari |

Ayrintili gerekce ve lisans metinleri: `docs/external_data.md`.

## Belgeler

| Dosya | Icerik |
|-------|--------|
| `docs/facts.md` | Dogrulanmis gercekler sicili (kaynak + tarih zorunlu) |
| `docs/experiments.md` | Deney gunlugu — negatif sonuclar dahil |
| `docs/external_data.md` | Kullanilan dis veri setleri + lisanslari (odul sartı) |
| `docs/reference/` | EUROCONTROL resmi ATXOT metodoloji dokumani + notlar |
| `docs/adr/` | Geri donusu pahali mimari kararlar |
| `docs/literature.md` | Literatur taramasi; her oznitelik ailesinin gerekcesi |
| `docs/paper/` | JOAS makale taslagi ve resmi LaTeX sablonu |

## Calistirma

```bash
python -m venv D:/prc-taxiout-2026/.venv
PY=D:/prc-taxiout-2026/.venv/Scripts/python.exe
$PY -m pip install -e ".[dev]"

# dis veri (yarisma verisi gerektirmez)
$PY -m taxiout.adapters.metar_iem --start 2025-01-01 --end 2026-08-01     --out D:/prc-taxiout-2026/00_raw/metar.parquet
$PY -m taxiout.adapters.airports --raw-dir D:/prc-taxiout-2026/00_raw

# yarisma verisi geldikten sonra
$PY scripts/probe_data.py     --data-dir D:/prc-taxiout-2026   # veri tanisi
$PY scripts/train_baseline.py --data-dir D:/prc-taxiout-2026   # mevsimsel dogrulama
$PY scripts/run_ablation.py   --data-dir D:/prc-taxiout-2026   # oznitelik ailesi tablosu
$PY scripts/make_submission.py --data-dir D:/prc-taxiout-2026 --team <takim-adi>

$PY -m pytest tests -q
```

Veri olmadan borulari surmek icin sentetik fixture:

```bash
$PY tests/make_fixture.py --out D:/prc-taxiout-2026/99_fixture/00_raw
$PY scripts/train_baseline.py --data-dir D:/prc-taxiout-2026/99_fixture --rounds 300
```

## Veri yerlesimi

Kod bu depoda (OneDrive ile yedeklenir). Veri ve modeller `D:/prc-taxiout-2026/` altinda —
C: surucusunde yalnizca %6 bos alan var ve DRAM-siz SSD, yazma hizi cokuyor.
`TAXIOUT_DATA_DIR` ortam degiskeni ile degistirilebilir.
