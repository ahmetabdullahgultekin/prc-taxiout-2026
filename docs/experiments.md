# Deney Gunlugu

Her satir bir GitHub issue'suna karsilik gelir. **Negatif sonuclar da yazilir** —
2025 jurisi, ise yaramayan seyleri raporlayan takimlari acikca ovdu. Bu tablo dogrudan
makalenin ablation bolumu olur.

Dogrulama semasi: 2025'ten Ocak ve Temmuz cikarilarak egitilir, o iki ayda **ayri ayri** dogrulanir.
Sebep: sıralama seti Ocak + Temmuz 2026 — iki mevsimsel uc.

| ID | Hipotez | Degisiklik | OOF RMSE (Oca / Tem / Toplam) | Delta | Karar | Commit |
|----|---------|-----------|-------------------------------|-------|-------|--------|
| E00 | veri tanisi | — | — | — | ✅ 15 gercek kaydedildi (facts R01-R15) | 42b6cd0 |
| E01 | (apt, stand, pist) ortalamasi | taban | — / — / **628,4** | referans | ✅ taban cizgi (probe §7) | 42b6cd0 |
| E02a | tam oznitelik seti, **ham** hedef | 95 oznitelik, 600 tur, 1 tohum | 423,60 / 240,80 / **378,80** | −249,6 | ✅ tut | 6b095f6 |
| E02b | tam oznitelik seti, **ATXOT P10 artigi** | ayni | 423,94 / 240,88 / **379,09** | +0,29 | ❌ **kazanc yok** | 6b095f6 |
| **v1** | ilk gonderim: ham hedef, 800 tur, 3 tohum | — | yerel 378,80 → **BOARD 331,23** | — | ✅ taban board skoru | 6b095f6 |
| E03a | uc degerleri egitimden cikar (>120 dk) | −4.180 satir | 455,11 / 236,25 / **402,92** | **+24,1** | ❌ **ZARARLI** | bc3c88f |
| E03b | uc degerleri egitimden cikar (>60 dk) | −7.249 satir | 467,53 / 249,29 / **415,07** | **+36,3** | ❌ **daha da zararli** | bc3c88f |

**Yerel ↔ board iliskisi (v1).** Yerel dogrulama 378,80, board 331,23: yerel olcum
**kotumser**, board %12,6 daha iyi. Bu guvenli yon. Muhtemel sebep 2025 Ocak/Temmuz
holdout'unun LIRF etiket hatalarini tam dozunda tasimasi. Onemli olan **siralamanin**
korunup korunmadigi; ikinci gonderimde test edilecek.

**E02b notu.** 2025 birincisinin en buyuk kazanci hedefi yeniden parametrelendirmekti
(yakit tuketimi → yakit akisi, 220,56 → 201,04). Buraya **transfer olmadi**: artik hedef
ham hedefle istatistiksel olarak ayni (0,29 sn fark, %0,08). Muhtemel sebep, oradaki
donusumun carpikligi azaltmasiydi; burada ise ATXOT referansi zaten agacin ilk
bolunmelerinde ogrendigi bir sabit ve cikarmak bilgi eklemiyor. Raporlanacak negatif
sonuc.

## Hatanin nerede oldugu (2026-09-01)

Toplam RMSE 378,80 ama **iki havalimani domine ediyor**:

| havalimani | RMSE | not |
|---|---:|---|
| LIRF | 966,5 | uc degerler |
| LFPG | 801,5 | uc degerler |
| EGLL | 297,8 | en uzun taxi (ort 22,7 dk) |
| LTFM | 228,2 | |
| LSZH | 220,6 | |
| EHAM | 201,0 | |
| EDDF | 189,4 | |
| EDDM | 187,6 | |
| LEMD | 165,5 | |
| LEBL | 151,1 | en kolay |

Ay bazinda: **Ocak 423,6 · Temmuz 240,8**. Ocak hem daha zor hem satirlarin %71'i.

### E03: uc degerleri egitimden cikarmak ZARARLI (beklenenin tersi)

| esik | egitim satiri | LIRF RMSE | toplam RMSE | Δ |
|---|---:|---:|---:|---:|
| yok | 1.870.367 | 966,5 | **378,80** | — |
| ≤120 dk | 1.866.187 | 1.149,4 | 402,92 | +24,1 |
| ≤60 dk | 1.863.118 | 1.205,0 | 415,07 | +36,3 |

Hipotez sunu diyordu: bu satirlar etiket hatasi, L2 kaybi tahmin edilemez gurultuyu
kovaliyor, cikarirsak bulguya daha iyi oturur. **Yanlis cikti** ve zarar esikle birlikte
buyuyor. LIRF'in kendi RMSE'si 966'dan 1.205'e cikiyor.

Aciklamasi: satirlar hatali olsa da modele **kuyrugun var oldugunu** ogretiyorlar.
Cikarinca model uzun taxi surelerini sistematik olarak dusuk tahmin ediyor, ve L2
altinda buyuk bir degeri dusuk tahmin etmenin bedeli cok agir. Dogrulama kumesi tam
kaldigi icin (board da tam) bu bedel dogrudan gorunuyor.

**Karar: filtre yok.** Uc degerler egitimde kalir. Ayrica bu, hedefi kirpmanin ya da
Huber gibi saglam bir kaybin da muhtemelen zarar verecegini soyluyor — RMSE ile
degerlendirilirken kuyrugu gormezden gelen her sey ayni tuzaga duser.

### Uc degerlerin kaynagi: etiket hatasi

| olcum | deger |
|---|---|
| 2 saati asan kalkis | 584 (%0,028) |
| bunlarin 480'i | LIRF'te |
| azami taxi-out | LIRF 131.167 sn (36,4 saat), LSZH 87.341, LFPG 84.240 |
| LIRF'te en ust %1'in varyans payi | **%88,1** (LFPG %48,3, EGLL %32,7) |
| 2 saati asanlarda NM eslesmesi olan | 103 |
| bunlarin NM'ye gore **makul** (<2sa) olani | **%94,2** (NM medyan 18 dk, APDF medyan 2,3 saat) |

Yani bu satirlarda taxi suresi uzun degil, **APDF blok saati yanlis**. Etiket hatasi.
PRC de resmi gostergesinde 120 dakikayi asanlari eliyor (ATXOT s.13 adim 1).

Sonucu: L2 kaybi tahmin edilemez gurultuyu koveliyor. **Siradaki deney (E03):** hedefi
esik asan satirlari yalnizca **egitimden** cikarmak; dogrulama tam kalir cunku board da
tam olacak. `train_baseline.py --max-train-sec <sn>`.

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
