# OPDI ADS-B yer olayları: değerlendirildi ve elendi

**Sonuç: kullanılamaz.** Gerekçe ve ölçüm aşağıda. Tekrar üretmek için:
`python scripts/probe_opdi_coverage.py --events <flight_events_*.parquet>`

## Neden bakıldı

Sıralama setinde kalkışların **blok çözülme anı** boşaltılmış (D05). OPDI — PRC'nin
kendi açık veri girişimi, OpenSky Network ile ortak — ADS-B'den türetilmiş uçuş
olayları yayımlıyor ve v0.0.2 ile **park pozisyonu giriş/çıkış** olayları eklendi.
`exit-parking_position`, boşaltılan alanın bağımsız bir ölçümü olurdu.

Kapsam **2022-01 → 2026-08-08**, yani her iki sıralama ayı da içeride. Veri açık,
belgeli ve PRC'nin kendi veri sayfasında listeleniyor; yarışma da amacını "açık veri
kullanmak" diye tanımlıyor. Yani meşruluk sorunu yok.

Dahası, yarışmanın gerekçesiyle birebir örtüşüyordu: taxi-out "elde etmesi zor bir
büyüklük" ve modelin gerçek işi, A-CDM verisi paylaşmayan havalimanlarındaki boşluğu
doldurmak. Açık ADS-B olaylarının o boşluğu doldurup dolduramayacağı doğrudan konuyla
ilgili bir sorudur.

## Ölçüm

10 günlük tek dosya (`flight_events_20260110_20260120.parquet`, 260 MB, 7,48M olay),
havalimanı merkezinin 10 km çevresindeki olaylar:

| havalimanı | exit-parking_position | take-off | entry-runway | entry-taxiway |
|---|---:|---:|---:|---:|
| LSZH | 9.611 | 1.412 | 7.121 | 42.816 |
| EDDF | 4.399 | 704 | 9.032 | 23.174 |
| LEBL | 7 | 853 | 4.875 | 2.045 |
| EGLL | 4 | 10 | 5.629 | 799 |
| EDDM | 2 | 31 | 2.359 | 342 |
| LEMD | 2 | 20 | 1.421 | 149 |
| LFPG | 1 | 1 | 1.684 | 69 |
| **EHAM** | **0** | 1.398 | 9.535 | 1.428 |
| **LIRF** | **0** | 7 | 781 | 77 |
| **LTAI** | **0** | 5 | 119 | 6 |
| **LTFM** | **0** | 0 | 25 | 9 |

Karşılaştırma için 10 günde beklenen kalkış sayısı havalimanı başına 3.000–7.500
mertebesinde (2025 resmî trafik verisinden).

## Yorum

Park pozisyonu olayları **yalnızca Zürih ve Frankfurt'ta** var. Sebep OPDI'nin
metodolojisinde: bu olaylar OpenStreetMap park pozisyonu poligonlarının H3 çözünürlük
12 ızgarasıyla eşleştirilmesiyle üretiliyor, ve o poligonlar havalimanlarının çoğunda
haritalanmamış. Ravizza ve arkadaşlarının OSM taxiway/park pozisyonu verisinin
yetersizliğinden şikâyet etmesiyle aynı sorun.

Ayrıca dikkat çekici: **LTFM ve LTAI'de açık ADS-B yer kapsaması neredeyse sıfır**
(10 günde 25 ve 119 pist girişi, kalkış olayı 0 ve 5). Yani ADS-B tabanlı herhangi bir
yaklaşım tam da iki Türk havalimanında çökerdi.

## Karar

Bu kaynak üzerine öznitelik **inşa edilmeyecek**. 11 havalimanının 2'sinde bulunan bir
öznitelik, modelin çoğunlukla eksik olarak taşıyacağı bir kolon olurdu; birleştirme
altyapısının maliyeti (uçuş eşleştirme, ~1,6 GB indirme) karşılığını vermez.

## Makaleye girecek hali

Bu, atılacak değil raporlanacak bir sonuç. 2025 jürisi, işe yaramayan yolları açıkça
raporlayan takımları övdü. Ayrıca PRC'nin kendi girişimi hakkında somut bir bulgu:
**açık ADS-B yer olayları, bugünkü kapsamıyla, eksik A-CDM blok saatlerinin yerini
tutamıyor** — çünkü sınırlayıcı olan ADS-B değil, OpenStreetMap'teki park pozisyonu
haritalamasının eksikliği. Bu, OPDI için eyleme dönüştürülebilir bir geri bildirimdir.
