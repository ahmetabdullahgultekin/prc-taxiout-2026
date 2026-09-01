# Veri Tani Raporu

Kaynak: `D:\prc-taxiout-2026\00_raw` - egitim dosyasi: 12

## 1. Sema karsilastirmasi (D05 / D06)

- egitim kolon sayisi: **30**, siralama: **30**
- siralamada olmayan kolonlar: yok
- siralamada fazladan olan kolonlar: yok
- submitting.parquet kolonlari: ['MVT_ID_mvt', 'TAXITIME_SEC_mvt']

**Siralama setinde DEP satirlarinda doluluk orani** (0.0 = tamamen bosaltilmis):

- DEP satir sayisi: **215,876**
- `FLIGHT_ID_mvt`: 0.9852
- `MVT_TIME_UTC_mvt`: 1.0000
- `BLOCK_TIME_UTC_mvt`: 0.0000  <-- BOSALTILMIS
- `SCHED_TIME_UTC_mvt`: 1.0000
- `RUNWAY_mvt`: 1.0000
- `STAND_mvt`: 1.0000
- `TAXITIME_SEC_mvt`: 0.0000  <-- BOSALTILMIS
- `LOBT_flt`: 0.9852
- `IOBT_flt`: 0.9852
- `EOBT_1_flt`: 0.9852
- `ARVT_1_flt`: 0.9852
- `AOBT_3_flt`: 0.9852  <-- **DOLU, kritik bulgu**
- `ARVT_3_flt`: 0.9852

## 2. Taxi-out kimligi: MVT_TIME - BLOCK_TIME == TAXITIME ? (D13)

- DEP satiri: **2,085,047**, ucu de dolu olan: **2,085,047**
- kimlik <1 sn hata ile tutan oran: **1.0000**
- en buyuk mutlak sapma: **0 sn**

Yorum: oran 1.0 ise TAXITIME turetilmis demektir ve zaman damgalari kendi icinde tutarlidir; 1.0 degilse aradaki fark bagimsiz bir olcum hatasidir ve kuyruk ozelliklerinin gurultu tabanini belirler.

## 3. Zaman damgasi hassasiyeti (M14)

| ADEP_mvt | n | mvt_second_is_zero | block_second_is_zero |
|---|---|---|---|
| EDDF | 230,141 | 0.0177 | 0.0169 |
| EDDM | 167,334 | 0.0831 | 0.0834 |
| EGLL | 239,546 | 0.0828 | 0.0838 |
| EHAM | 247,951 | 0.0173 | 0.0169 |
| LEBL | 179,705 | 0.0166 | 0.0830 |
| LEMD | 212,242 | 0.0164 | 0.0837 |
| LFPG | 239,552 | 0.0832 | 0.0828 |
| LIRF | 160,704 | 0.0838 | 0.0835 |
| LSZH | 134,907 | 0.0168 | 0.0198 |
| LTFM | 272,965 | 0.0833 | 0.0830 |

Oran ~1.0 olan havalimaninda veri **HH:MM** hassasiyetindedir: taxi-out'ta +-60 sn taban gurultu vardir ve o havalimani icin ulasilabilir RMSE alt siniri daha yuksektir.

## 4. Network Manager eslesme orani (D10)

**egitim 2025**

| ADEP_mvt | n | flight_id_filled | aobt3_filled |
|---|---|---|---|
| EDDF | 230,141 | 0.9915 | 0.9915 |
| EDDM | 167,334 | 0.9940 | 0.9940 |
| EGLL | 239,546 | 0.9941 | 0.9941 |
| EHAM | 247,951 | 0.9835 | 0.9835 |
| LEBL | 179,705 | 0.9897 | 0.9896 |
| LEMD | 212,242 | 0.9956 | 0.9955 |
| LFPG | 239,552 | 0.9843 | 0.9842 |
| LIRF | 160,704 | 0.9907 | 0.9907 |
| LSZH | 134,907 | 0.9830 | 0.9830 |
| LTFM | 272,965 | 0.9867 | 0.9866 |

**siralama 2026**

| ADEP_mvt | n | flight_id_filled | aobt3_filled |
|---|---|---|---|
| EDDF | 36,317 | 0.9884 | 0.9884 |
| EDDM | 10,953 | 0.9891 | 0.9891 |
| EGLL | 39,840 | 0.9938 | 0.9938 |
| EHAM | 38,182 | 0.9684 | 0.9684 |
| LEBL | 12,201 | 0.9937 | 0.9937 |
| LEMD | 16,802 | 0.9963 | 0.9963 |
| LFPG | 18,129 | 0.9821 | 0.9821 |
| LIRF | 11,061 | 0.9903 | 0.9903 |
| LSZH | 9,995 | 0.9700 | 0.9700 |
| LTFM | 22,396 | 0.9852 | 0.9851 |


## 5. KRITIK: AOBT_3_flt ne kadar iyi bir tahmin? (Q02)

Naif tahminci: `taxi_out = MVT_TIME_UTC_mvt - AOBT_3_flt`

| n | rmse | mae | bias | median_abs_error |
|---|---|---|---|---|
| 2,062,577 | 384.9 | 238.1 | 17.0 | 175.0 |

| ADEP_mvt | n | rmse | bias |
|---|---|---|---|
| EDDF | 228,185 | 255.1 | 53.2 |
| LSZH | 132,616 | 268.4 | -59.4 |
| LEMD | 211,295 | 276.4 | -33.9 |
| LEBL | 177,843 | 311.4 | -67.5 |
| EHAM | 243,867 | 329.6 | 151.7 |
| EDDM | 166,324 | 348.9 | -81.8 |
| LFPG | 235,779 | 379.5 | -35.4 |
| EGLL | 238,132 | 418.5 | 22.7 |
| LTFM | 269,320 | 530.6 | 236.4 |
| LIRF | 159,216 | 557.4 | -214.2 |

**Nasil okunur.** Bu RMSE dusukse (orn. <60 sn) yarisma buyuk olcude 'NM blok saatini APDF blok saatiyle uzlastirma + eslesmeyen satirlari doldurma' problemidir ve tum mimari buna gore kurulur. Yuksekse (orn. >200 sn) AOBT_3 yalnizca guclu bir ozelliktir, cozum degildir. Kapsama orani (n / total DEP) en az RMSE kadar onemli: kapsanmayan satirlar icin ayri bir model gerekir.

## 6. Hedef dagilimi

| ADEP_mvt | n | mean | std | p10 | p50 | p99 | over_120min_share | negative_share |
|---|---|---|---|---|---|---|---|---|
| EDDF | 230,141 | 863.5 | 329.8 | 478.0 | 837.0 | 1,819.0 | 0.0000 | 0.0000 |
| EDDM | 167,334 | 811.9 | 301.8 | 533.0 | 774.0 | 1,921.0 | 0.0000 | 0.0000 |
| EGLL | 239,546 | 1,364.2 | 421.8 | 909.0 | 1,319.0 | 2,701.0 | 0.0002 | 0.0000 |
| EHAM | 247,951 | 784.6 | 318.5 | 458.0 | 742.0 | 1,775.0 | 0.0000 | 0.0000 |
| LEBL | 179,705 | 956.5 | 330.9 | 595.0 | 906.0 | 1,962.0 | 0.0000 | 0.0000 |
| LEMD | 212,242 | 1,014.7 | 312.5 | 656.0 | 985.0 | 1,932.0 | 0.0000 | 0.0000 |
| LFPG | 239,552 | 1,019.5 | 453.0 | 655.0 | 954.0 | 2,409.0 | 0.0002 | 0.0003 |
| LIRF | 160,704 | 1,194.6 | 1,332.0 | 670.0 | 1,025.0 | 4,019.0 | 0.0030 | 0.0000 |
| LSZH | 134,907 | 740.5 | 385.4 | 400.0 | 711.0 | 1,707.0 | 0.0000 | 0.0022 |
| LTFM | 272,965 | 1,053.0 | 427.6 | 662.0 | 963.0 | 2,587.0 | 0.0001 | 0.0000 |

`over_120min_share` PRC'nin resmi filtresini asan orandir (M08); `negative_share` veri hatasi isaretidir. Ikisi de RMSE'de agir cezalandirilan kuyruktur: kirpma degil, **modelleme** karari gerektirir.

**Aylik (Ocak ve Temmuz satirlarina dikkat: siralama seti o iki ay):**

| ay | n | mean | std |
|---|---|---|---|
| 1 | 153,706 | 995.3 | 604.8 |
| 2 | 143,732 | 1,002.4 | 628.3 |
| 3 | 164,449 | 972.0 | 461.7 |
| 4 | 175,288 | 971.4 | 436.0 |
| 5 | 185,202 | 986.6 | 469.4 |
| 6 | 183,142 | 973.2 | 554.9 |
| 7 | 190,713 | 1,025.7 | 745.0 |
| 8 | 191,182 | 993.8 | 533.8 |
| 9 | 183,950 | 989.8 | 560.3 |
| 10 | 185,674 | 992.0 | 437.1 |
| 11 | 162,332 | 997.0 | 532.0 |
| 12 | 165,677 | 995.0 | 514.7 |

## 7. Temel modeller ve soguk baslangic

| n_validation | combo_coverage | rmse_global_mean | rmse_airport_mean | rmse_combo_mean |
|---|---|---|---|---|
| 344,419 | 0.9986 | 686.6 | 660.0 | 628.4 |

`rmse_combo_mean` ilk gercek gonderimimizin tahmini seviyesidir. Bunun uzerine koyacagimiz her sey kuyruk / tikaniklik / weather bilesenidir.

**Siralama setinin egitimde gorulmemis kombo orani (soguk baslangic riski):**

| n | seen_combo_share | stand_null_share | runway_null_share |
|---|---|---|---|
| 215,876 | 0.9946 | 0.0000 | 0.0000 |

## 8. Ikinci tutamak: planlanan blok saati (SCHED_TIME)

Kimlik: `MVT_TIME - SCHED_TIME = taxi_out + kalkis_gecikmesi`.
`SCHED_TIME_UTC_mvt` siralama setinde bosaltilmamis (D05), yani bu da mesru bir
ozniteliktir. Degeri tamamen **kalkis gecikmesinin ne kadar ongorulebilir**
olduguna bagli: delay_sec dar dagilirsa hedefi neredeyse verir, genis dagilirsa
yalnizca bir ust sinir olur.

**Kalkis gecikmesi (gercek blok - planlanan blok), saniye:**

| n | mean | std | p10 | p50 | p90 | early_share |
|---|---|---|---|---|---|---|
| 2,085,047 | 901.3 | 2,238.0 | -242.0 | 415.0 | 2,396.0 | 0.2421 |

**`MVT - SCHED` naif tahmincisi (gecikmeyi sifir sayar):**

| rmse | bias |
|---|---|
| 2,412.7 | 901.3 |

Karsilastir: 5. bolumdeki AOBT_3 naif tahmincisi. Iki tutamaktan hangisi daha
dar, ikisi birlikte ne kadar kaliyor — mimari karari budur. Gecikmenin std'si
bu problemde **indirgenemez belirsizligin buyuk kismini** olusturuyor olabilir.
