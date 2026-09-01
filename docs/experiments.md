# Deney Gunlugu

Her satir bir GitHub issue'suna karsilik gelir. **Negatif sonuclar da yazilir** —
2025 jurisi, ise yaramayan seyleri raporlayan takimlari acikca ovdu. Bu tablo dogrudan
makalenin ablation bolumu olur.

Dogrulama semasi: 2025'ten Ocak ve Temmuz cikarilarak egitilir, o iki ayda **ayri ayri** dogrulanir.
Sebep: sıralama seti Ocak + Temmuz 2026 — iki mevsimsel uc.

| ID | Hipotez | Degisiklik | OOF RMSE (Oca / Tem / Toplam) | Delta | Karar | Commit |
|----|---------|-----------|-------------------------------|-------|-------|--------|
| — | _gercek veri bekleniyor_ | — | — | — | — | — |

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
