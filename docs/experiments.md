# Deney Gunlugu

Her satir bir GitHub issue'suna karsilik gelir. **Negatif sonuclar da yazilir** —
2025 jurisi, ise yaramayan seyleri raporlayan takimlari acikca ovdu. Bu tablo dogrudan
makalenin ablation bolumu olur.

Dogrulama semasi: 2025'ten Ocak ve Temmuz cikarilarak egitilir, o iki ayda **ayri ayri** dogrulanir.
Sebep: sıralama seti Ocak + Temmuz 2026 — iki mevsimsel uc.

| ID | Hipotez | Degisiklik | OOF RMSE (Oca / Tem / Toplam) | Delta | Karar | Commit |
|----|---------|-----------|-------------------------------|-------|-------|--------|
| — | _gercek veri bekleniyor_ | — | — | — | — | — |

## Veri gelmeden kapatilan yollar (negatif sonuclar)

| Yol | Neden bakildi | Sonuc | Belge |
|-----|---------------|-------|-------|
| OPDI ADS-B park pozisyonu olaylari | Bosaltilan blok saatinin bagimsiz olcumu olurdu; acik ve belgeli veri | **ELENDI** — olaylar 11 havalimaninin yalnizca 2'sinde (LSZH, EDDF) var; LTFM/LTAI'de ADS-B yer kapsamasi sifira yakin | `docs/opdi_negative_result.md` |
| EUROCONTROL varis ATFM gecikmesinde `D` (de-icing) neden kodu | Gunluk, dogrudan de-icing olcumu olurdu | **ELENDI** — kolon tamamen bos; de-icing bir *varis* ATFM nedeni olarak kodlanmiyor | `docs/external_data.md` |
| EUROCONTROL resmi taxi-out gostergesini **oznitelik** olarak kullanmak | Havalimani-ay bazinda referans/ek sure | **ELENDI** — aylik, ~2 ay gecikmeli yayim, Temmuz 2026 kapsanmiyor; ayrica dairesel olurdu. **Dogrulama icin kullaniliyor** | `docs/deicing_analysis.md` |

## Veri gelir gelmez kosulacak sira

Bu sira rastgele degil: 2025 birincisinin ablation tablosu (P06) makalenin katkı
sunumunun ta kendisiydi, ve o tabloyu **dogrudan siralama seti uzerinde** urettiler (P04).
Yani gonderimlerimiz ayar denemesi degil, **tasarlanmis bir deney** olmali.

| Sira | Deney | Neden once bu | Komut |
|------|-------|---------------|-------|
| E00 | Veri tanisi | Mimariyi belirleyen sorular burada cevaplaniyor (Q02, D13, M14) | `scripts/probe_data.py` |
| E01 | (apt, stand, pist) ortalamasi | Ilk gecerli gonderim + RMSE tabani | `train_baseline.py` icindeki taban |
| E02 | Ham hedef vs ATXOT artigi | 2025'te en buyuk tekil kazanc bu turden bir yeniden parametrelendirmeydi (P05) | `train_baseline.py` (ikisini birden kosar) |
| E03 | `AOBT_3_flt` var / yok | NM blok saatinin gercek bilgi degeri; tum mimariyi belirler | `--no-aobt3` |
| E04 | Tikaniklik oznitelikleri var / yok | Isin fikri cekirdegi; en buyuk kazanc buradan beklenir | oznitelik grubu kapatilarak |
| E05 | METAR var / yok, ozellikle Ocak | LSZH/EHAM/EDDM/LTFM Ocak'ta %10-18 de-icing kosulunda (W03) | METAR dosyasi gizlenerek |
| E06 | Havalimani bazli model vs global | LTFM/LTAI ile LSZH ayni davranmaz | — |
| E07 | Mevsimsel uzmanlasma (kis/yaz) | Siralama seti iki mevsimsel uc | — |
| E08 | `SCHED_TIME` tutamagi var / yok | `MVT − SCHED = taxi + gecikme`; degeri gecikmenin dagilimina bagli (A01-A03) | `run_ablation.py` (`atfm` ailesi) |
| E09 | Tohum ortalamasi (5 model) | 2024 birincisinin yontemi: ayni veri, ayni hiperparametre, farkli tohum | `--seeds 5` |

## Ablation nasil kosulur

```bash
PY=D:/prc-taxiout-2026/.venv/Scripts/python.exe
$PY scripts/run_ablation.py --data-dir D:/prc-taxiout-2026 --rounds 1200 --seeds 3
$PY scripts/run_ablation.py --data-dir D:/prc-taxiout-2026 --causal      # makale icin
$PY scripts/run_ablation.py --data-dir D:/prc-taxiout-2026 --raw-target  # E02 karsilastirmasi
```

Her aile icin bir kosu; cikti `docs/ablation_report.md` (git'e girmez, her kosuda
yeniden uretilir). Negatif Δ o aileyi cikarmanin RMSE'yi **dusurdugu** anlamina gelir —
yani aile zarar veriyordur ve bu da raporlanacak bir sonuctur.

**Uyari.** Sentetik fixture uzerindeki ablation sayilari anlamsizdir; yalnizca borularin
calistigini gosterir. Fixture'in kendi uretim sureci bazi aileleri yapay olarak baskin
gosterir (ornegin `SCHED_TIME` sabit ofsetliyken `atfm` ailesi hedefi birebir
sizdiriyordu — 2026-09-01'de duzeltildi).
