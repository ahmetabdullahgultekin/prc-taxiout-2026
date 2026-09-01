# De-icing rejimi: METAR vekilinin bagimsiz dogrulanmasi

Uretildigi komut: `python scripts/analyse_deicing.py --raw-dir <yol>`
**Yarisma verisi kullanilmaz** — iki acik kaynak: IEM METAR ve EUROCONTROL'un
yayimladigi Taxi-Out Additional Time gostergesi. Kapsam: 180 havalimani-ay.

## Neden bu karsilastirma anlamli

PRC resmi gostergesinde **AOBT sonrasi de-icing yapan ucuslari hesaptan atiyor**
(ATXOT s.13, adim 1). Dolayisiyla gostergenin "gecerli referansi olmayan ucus orani"
alani, kis aylarinda buyuk olcude de-icing'i tasir. Bu, METAR'dan turettigimiz
`deicing_vekili` alani icin **bagimsiz** bir olcumdur.

## Sonuc: vekil calisiyor

Tum veri uzerinde korelasyon **r = 0.757** (de-icing vekili ↔ referanssiz
ucus orani). Havalimani icinde, aylar arasinda:

| apt | ay_sayisi | r_referanssiz | r_ek_sure | ort_deicing | ort_referanssiz |
|---|---|---|---|---|---|
| LTFM | 18 | 0.982 | -0.061 | 0.020 | 0.010 |
| LSZH | 18 | 0.967 | -0.392 | 0.025 | 0.037 |
| EDDF | 18 | 0.943 | -0.156 | 0.010 | 0.015 |
| EDDM | 18 | 0.936 | -0.355 | 0.029 | 0.072 |
| LFPG | 18 | 0.873 | -0.116 | 0.005 | 0.020 |
| LEMD | 18 | 0.820 | -0.375 | 0.001 | 0.005 |
| LIRF | 18 | 0.470 | -0.009 | 0.000 | 0.003 |
| LEBL | 18 | 0.302 | 0.194 | 0.000 | 0.001 |
| EGLL | 18 | 0.275 | -0.109 | 0.001 | 0.000 |
| EHAM | 18 | 0.009 | 0.982 | 0.017 | 0.010 |

Soguk havalimanlarinda korelasyon 0.87–0.98; sicak olanlarda (LIRF, LEBL, EGLL)
de-icing neredeyse hic olmadigi icin korelasyon gurultudur, dusuk olmasi beklenir.

## Asil bulgu: havalimanlarinin de-icing rejimi farkli

De-icing vekili ile **ek taxi-out suresi** arasindaki korelasyon genelde
-0.131, yani neredeyse yok — ama havalimani bazinda tablo ikiye ayriliyor:

| apt | r_ek_sure | kis_ek_sure | yaz_ek_sure | kis_yaz_farki |
|---|---|---|---|---|
| LTFM | -0.061 | 4.52 | 5.13 | -0.60 |
| LSZH | -0.392 | 3.12 | 3.51 | -0.39 |
| EDDF | -0.156 | 3.34 | 3.59 | -0.25 |
| EDDM | -0.355 | 2.81 | 3.66 | -0.86 |
| LFPG | -0.116 | 3.78 | 4.50 | -0.72 |
| LEMD | -0.375 | 3.23 | 4.03 | -0.81 |
| LIRF | -0.009 | 5.29 | 8.12 | -2.82 |
| LEBL | 0.194 | 3.11 | 4.18 | -1.07 |
| EGLL | -0.109 | 6.03 | 6.80 | -0.77 |
| EHAM | 0.982 | 4.40 | 2.94 | 1.46 |

**EHAM tek basina ayri duruyor.** Amsterdam'da referanssiz ucus orani yil boyunca
sabit (~%1) kaliyor ama ek taxi-out suresi kisin belirgin sekilde artiyor. EDDM ve
LSZH'de ise tam tersi: kisin ucuslarin buyuk bolumu gostergeden **dusuyor**
(Munih'te Ocak 2026'da %31), ek sure ise artmiyor.

Onemli bir kayit: ek taxi-out suresi **her havalimaninda** kisin yazdan dusuk
(-0,25 ile -2,82 dk arasi), cunku yaz trafik zirvesi kuyrugu buyutuyor. EHAM'in
+1,46 dk'lik farki bu tabana ragmen olusuyor; yani anomaliyi zayiflatan degil,
guclendiren bir arka plan.

Yorum: kis gecikmesinin **ne kadarinin taxi-out'un icine dustugu** havalimanina gore
degisiyor. Amsterdam'da icine dusuyor ve hedefi buyutuyor; Munih ve Zurih'te etkilenen
ucuslar isaretlenip resmi hesaptan cikariliyor.

Bu, kesin bir nedensellik iddiasi degil: elimizde de-icing kayitlari yok, yalnizca hava
kosulu vekili ile resmi gostergenin iki alani var. Ancak iki bagimsiz kaynagin ayni
mevsimsel yapiyi gostermesi ve havalimanlarinin iki farkli desene ayrilmasi, yarisma
verisi geldiginde **ilk sinanacak hipotezi** belirlemek icin yeterli.

## Bizim icin sonucu

Biz **ham taxi-out'u** tahmin ediyoruz ve hicbir satiri atamayiz. Yani:

- EHAM'da hava etkisi dogrudan hedefte gorunur ve ogrenilebilir.
- EDDM ve LSZH'de, resmi gostergenin **attigi** ucuslar bizim veri setimizde duruyor ve
  uc degerler olarak Ocak hatamizi domine edecek. Yayimlanmis hicbir taxi-out modeli bu
  ucuslari tahmin etmek zorunda kalmadi, cunku standart metodoloji onlari eliyor.
- Hava etkisi **havalimanina gore degisiyor**; global bir hava katsayisi yerine
  havalimani x hava etkilesimi (ya da havalimani bazli model) gerekiyor.

## Kapsam disi

Resmi gostergede **hic verisi olmayan** havalimani: LTAI
Antalya EUROCONTROL performans semasinda degil; bu havalimani icin dis dogrulama
kaynagimiz yok ve veri kalitesinin farkli olabilecegi akilda tutulmali.

Siralama aylarindan **Temmuz 2026 henuz yayimlanmamis** (seri Haziran 2026'da bitiyor),
dolayisiyla bu gosterge ozellik olarak kullanilamaz — yalnizca dogrulama icindir.
