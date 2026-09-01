# PRC Data Challenge 2026 — Taxi-Out Time Prediction

11 buyuk Avrupa havalimaninda kalkis yapan ucaklarin **taxi-out suresini** (AOBT -> ATOT, saniye)
tahmin eden acik kaynakli cozum. EUROCONTROL Performance Review Commission (PRC) ve
OpenSky Network tarafindan duzenlenen 2026 veri yarismasi icin.

- Yarisma: <https://ansperformance.eu/study/data-challenge/dc2026/>
- Metrik: RMSE (saniye), Ocak + Temmuz 2026 kalkislari uzerinde
- Lisans: GNU GPLv3 (yarisma odul sartı)

## Durum

Kurulum asamasi. Veri erisimi icin takim olusturma basvurusu bekleniyor.

## Belgeler

| Dosya | Icerik |
|-------|--------|
| `docs/facts.md` | Dogrulanmis gercekler sicili (kaynak + tarih zorunlu) |
| `docs/experiments.md` | Deney gunlugu — negatif sonuclar dahil |
| `docs/external_data.md` | Kullanilan dis veri setleri + lisanslari (odul sartı) |
| `docs/reference/` | EUROCONTROL resmi ATXOT metodoloji dokumani + notlar |
| `docs/adr/` | Geri donusu pahali mimari kararlar |

## Calistirma

```bash
python -m venv D:/prc-taxiout-2026/.venv
D:/prc-taxiout-2026/.venv/Scripts/python -m pip install -e .
python scripts/probe_data.py --data-dir D:/prc-taxiout-2026
```

## Veri yerlesimi

Kod bu depoda (OneDrive ile yedeklenir). Veri ve modeller `D:/prc-taxiout-2026/` altinda —
C: surucusunde yalnizca %6 bos alan var ve DRAM-siz SSD, yazma hizi cokuyor.
`TAXIOUT_DATA_DIR` ortam degiskeni ile degistirilebilir.
