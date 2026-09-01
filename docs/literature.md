# Literatür: taxi-out süresi tahmini

Tarama 2026-09-01'de OpenAlex üzerinden yapıldı (başlık bazlı, 136 alakalı kayıt;
ham çıktı `scratchpad/papers/openalex_taxiout.json`). Buradaki her satır okunmuş bir
özete dayanıyor; okunmamış olan açıkça öyle işaretli.

Bu dosyanın iki işi var: **(1)** her öznitelik ailesinin neden seçildiğini kaynağa
bağlamak — 2025 jürisi "öznitelik seçimi için yetersiz gerekçe" diye açıkça eleştirdi;
**(2)** JOAS makalesinin ilgili-çalışmalar bölümünün taslağı olmak.

---

## 1. Kuyruk ekolü — problemin fiziği

**Idris, Clarke, Bhuva, Kang (2002), "Queuing Model for Taxi-Out Time Estimation",
*Air Traffic Control Quarterly* 10(1). 176 atıf.** ([doi](https://doi.org/10.2514/atcq.10.1.1))

Boston Logan'da taxi-out'u belirleyen dört ana nedensel faktör: **pist konfigürasyonu,
havayolu/terminal, aşağı-akış kısıtları (downstream restrictions) ve kalkış kuyruğu
büyüklüğü.** Bunlardan **kuyruk büyüklüğü en önemlisi**; tanımı: uçağın push-back'i ile
kendi kalkışı arasında gerçekleşen kalkış sayısı.

Kritik nokta: modelleri kuyruk büyüklüğünü **tahmin etmek** zorunda, çünkü uçağın taxi
sırasında ne kadar "geçilme" (passing) yaşayacağı bilinmiyor. Karşılaştırma tabanı
14 günlük hareketli ortalama (ETMS'in o zamanki üretim yöntemi).

> **Bizim için anlamı.** Bu değişken bizde **gözlenebilir**: sıralama setinde her
> kalkışın kalkış saati duruyor. Ama tam sayımı push-back saatini gerektirir, o da
> hedefimiz — bu yüzden `congestion.py` sabit pencereli (5/10/15/30/60 dk) dairesel
> olmayan vekiller kullanıyor. Dört faktörün üçü doğrudan uyguladığımız öznitelikler:
> pist konfigürasyonu, operatör/stand, kuyruk yoğunluğu.

**Simaiakis & Balakrishnan (2015), "A Queuing Model of the Airport Departure Process",
*Transportation Science*. 108 atıf.** ([doi](https://doi.org/10.1287/trsc.2015.0603))

Taxi-out'u **engelsiz taxi-out + kalkış kuyruğu + tıkanıklık gecikmesi** olarak
ayrıştırır; pist kuyruğunu D/Eₖ/1 sisteminin geçici (transient) analiziyle modeller.
_(Özet okundu; tam metin okunmadı.)_

---

## 2. Engelsiz (unimpeded) süre — PRC'nin yöntemine doğrudan eleştiri

**Yin ve ark. (2017), "Methods for determining unimpeded aircraft taxiing time and
evaluating airport taxiing performance", *Chinese Journal of Aeronautics* 30(2).
43 atıf, açık erişim.** ([doi](https://doi.org/10.1016/j.cja.2017.01.002))

Bu makale **tam olarak PRC'nin kullandığı türden yöntemleri gözden geçirip yerine
regresyon öneriyor**. Bulguları:

- Farklı ANSP'lerin yaygın yöntemleri (yüzdelik tabanlı referanslar) inceleniyor ve
  **ekonometrik regresyon modelleri güçlü biçimde öneriliyor** — daha az ayrıntılı veri
  gerektiriyor ve genel performans analizine yetiyor.
- Önerilen model mevcutları geçiyor çünkü **daha fazla açıklayıcı değişken** ekliyor:
  özellikle **uçakların birbirini geçmesi (passing/over-passing)** kuyruk uzunluğu
  hesabına katılıyor, ayrıca **pist konfigürasyonu, ground delay programı ve weather
  durumu** modele giriyor.
- Ana sonuç: **"taxiway sistemindeki kuyruk uzunluğu ve kuyruklar arası etkileşim uzun
  taxi-out sürelerinin başlıca katkı sağlayıcılarıdır."**

> **Bizim için anlamı — bu, tezin çekirdeği.** PRC'nin resmî göstergesi (ATXOT) referansı
> stand-pist kombosunun **P10'u** olarak tanımlıyor ve uçak tipini bilerek dışarıda
> bırakıyor (bkz. `atxot-notes.md` M10, M11). Literatür ise tam bu noktada regresyonun
> üstün olduğunu söylüyor. Katkımız spekülatif bir boşluğa değil, **kurumun kendi
> belgelediği ve literatürün adını koyduğu** bir boşluğa oturuyor.

---

## 3. Avrupa havalimanlarında yerleşim tabanlı regresyon

**Ravizza, Atkin, Maathuis, Burke (2013), "A combined statistical approach and ground
movement model for improving taxi time estimations at airports", *JORS* 64(9).
74 atıf.** ([doi](https://doi.org/10.1057/jors.2012.123))

İki büyük Avrupa hub'ında (**Stockholm-Arlanda ve Zürih**) çoklu doğrusal regresyon:
havalimanı yerleşimi + geçmiş taxi süreleri. Motivasyon bizimkiyle aynı sorunun tersi:
geçmiş verideki **havalimanı yükü etkisini nicelleştirip ayıklamak**.

**Ravizza, Atkin, Burke (2013), "Aircraft taxi time prediction: Comparisons and insights",
*Applied Soft Computing*. 64 atıf.** ([doi](https://doi.org/10.1016/j.asoc.2013.10.004))

TSK bulanık kural tabanlı sistem, SVM regresyon / M5 model ağaçları / klasik
regresyonun üzerine çıkıyor. **ARN'de %58,21, ZRH'de %64,05 oranında ±1 dakika
doğruluk.** _(Sayılar aramadan; tam metin okunmadı.)_

**LSZH bizim veri setimizde.** Bu, sahip olduğumuz tek doğrudan karşılaştırılabilir
ZRH referansı: **±1 dk içinde ~%64**.

**Ravizza ve ark. (2020), "Aircraft taxi time prediction: Feature importance and their
implications", *Transportation Research Part C* 112. 70 atıf.**
([doi](https://doi.org/10.1016/j.trc.2020.102892))

En önemli öznitelikler: **taxi mesafesi, dönüş açılarının toplamı, kalkış/varış ayrımı
ve uçak taxi yaparken ortamdaki trafik miktarı.** _(Özet erişilemedi; bulgu arama
sonucundan, tam metin okunmadı — makalede alıntılamadan önce doğrula.)_

> **Bizim için anlamı.** Taxi mesafesi ve dönüş açısı bizde **yok** (rota verisi yok).
> Ama ampirik P10, o stand-pist çifti için gerçekte kullanılan rotanın süresini içerir —
> teorik en kısa yoldan daha iyi bir vekildir. OSM taxiway grafiği bu yüzden çekirdek
> değil, yalnızca seyrek hücreler için geri düşüş adayı.

---

## 4. Makine öğrenmesi uygulamaları — hangi öznitelikler, hangi hata

**Herrema ve ark. (2018), "Taxi-Out Time Prediction Model at Charles de Gaulle Airport",
*Journal of Aerospace Information Systems*. 37 atıf.**
([doi](https://doi.org/10.2514/1.i010502))

**LFPG bizim veri setimizde.** Sinir ağı, regresyon ağacı, pekiştirmeli öğrenme ve MLP
karşılaştırılıyor; metrik olarak RMSE seçilmiş. **En iyi yöntem regresyon ağacı,
herhangi bir günde ortalama hata ≈ 1,6 dakika (≈ 96 saniye).**

> Bu, sahip olduğumuz **en somut hedef büyüklük**: bizim havalimanlarımızdan birinde,
> aynı metrikle, yayınlanmış bir sonuç. 11 heterojen havalimanı ve rota verisi olmadan
> daha kötüsü beklenir; ama büyüklük mertebesini verir.

**Lee, Malik, Jung (2016), "Taxi-Out Time Prediction for Departures at Charlotte Airport
Using Machine Learning Techniques", AIAA ATIO. 53 atıf.**
([doi](https://doi.org/10.2514/6.2016-3910))

Seçilen değişkenler: **terminal concourse, spot, pist, departure fix ve ağırlık sınıfı**;
ayrıca farklı trafik akışı ve weather koşulları. Doğrusal regresyon ve rastgele orman en
iyi RMSE'yi veriyor.

> **Yeni öznitelik fikri buradan çıktı: departure fix.** Aynı çıkış noktasına/yönüne
> giden kalkışlar birbirinden daha fazla ayrılmak zorundadır (rota ve girdap ayırması),
> dolayısıyla komşuları kendisiyle aynı yöne gidiyorsa uçak daha çok bekler. Bizde
> departure fix yok, ama `ADES_mvt` var: kalkış havalimanından varış havalimanına
> **kerteriz** hesaplanıp sektöre yuvarlanabilir ve penceredeki aynı-sektör kalkış
> sayısı sayılabilir. `features/routing.py` bunu yapıyor.

**Wang ve ark. (2018), "Machine Learning Techniques for Taxi-out Time Prediction with a
Macroscopic Network Topology", DASC. 30 atıf.**
([doi](https://doi.org/10.1109/dasc.2018.8569664))

Şangay Pudong. Tahmin edicileri **dört aileye** ayırıyor — bu taksonomiyi olduğu gibi
benimseyip makalede atıfla kullanacağız:

| Aile | Açılım | Bizdeki karşılığı |
|------|--------|-------------------|
| SIFI | surface **instantaneous** flow indices | `apt_dep_prev_5m`, `apt_arr_prev_5m` |
| SCFI | surface **cumulative** flow indices | 30/60 dk pencereleri |
| AQLI | aircraft **queue length** indices | `pist_kalkis_onceki_*`, `rwy_service_interval_sec` |
| SRDI | **slot resource demand** indices | `sched_offset_sec`, ATFM sürüklenmesi (LOBT−IOBT) |

Bir aylık örnekle eğitilen rastgele orman, bir günlükle eğitilenleri belirgin biçimde
geçiyor — örnek boyutu kritik. Bizde bir yıl var.

**Diana (2018), "Can machines learn how to forecast taxi-out time? … Seattle/Tacoma",
*Transportation Research Part E* 119. 39 atıf.**
([doi](https://doi.org/10.1016/j.tre.2018.10.003)) _(Özet erişilemedi.)_

**Balakrishna, Ganesan, Sherry (2010), "Accuracy of reinforcement learning algorithms
for predicting aircraft taxi-out times: Tampa Bay", *TR-C* 18(6). 116 atıf.**
([doi](https://doi.org/10.1016/j.trc.2010.03.003)) _(Özet erişilemedi.)_

---

## 5. Boşluklar — katkımızın oturduğu yer

1. **Ölçek ve heterojenlik.** Yukarıdaki çalışmaların hemen hepsi **tek havalimanı**
   (Logan, CDG, Charlotte, Pudong, Seattle, ZRH+ARN). 11 havalimanını tek çatı altında,
   ortak öznitelik tanımlarıyla modelleyen bir çalışma bulamadık. LTFM ve LTAI üzerine
   yayınlanmış taxi-out çalışması **hiç** bulunamadı.
2. **Retrospektif gözlenebilirlik.** Idris'in kuyruk değişkeni operasyonda tahmin
   edilmek zorunda; post-ops kurguda gözlenebilir. Bu farkın **bilgi değerini ölçen**
   bir çalışma görmedik. Makalede iki model varyantı (retrospektif / nedensel)
   raporlanacak; aradaki RMSE farkı, gerçek zamanlı sistemler için ulaşılabilir
   iyileştirmenin üst sınırıdır.
3. **De-icing.** PRC resmî göstergede AOBT sonrası de-icing yapan uçuşları **eliyor**
   (ATXOT s.13). Ham taxi-out tahmininde bu satırlar elenemez. Ocak 2026'da de-icing
   koşulu oranı LSZH %18 · EHAM %13 · EDDM %11 · LTFM %10 (kendi METAR analizimiz, W03).
   Bu rejimi açıkça modelleyen bir taxi-out çalışması görmedik.

## Doğrulanması gereken alıntılar

Makalede kullanmadan önce tam metni okunacaklar (şu an yalnızca özet/arama düzeyinde):

- Ravizza 2020 öznitelik önem sıralaması (dspace/storre 403 döndü, kurumsal erişim gerek)
- Ravizza 2013 ±1 dk doğruluk sayıları (%58,21 / %64,05)
- Diana 2018, Balakrishna 2010, Simaiakis 2015 tam metinleri
