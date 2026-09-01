# Doğrulanmış Gerçekler Sicili

Kural: **kaynaksız ve tarihsiz satır yazma.** Her ✅ satırı haftada bir yeniden kontrol edilir.
Yarışma sayfası "kuralları değiştirme veya yarışmayı durdurma hakkını saklı tutuyoruz" diyor — bugün doğru olan yarın yanlış olabilir.

Durumlar: ✅ doğrulandı · ⏳ veri gelince ölçülecek · ⚠️ teyit gerek · 🔴 açık sorun · ❌ yanlış çıktı

## Yarışma kuralları

| # | Gerçek | Kaynak | Kontrol | Durum |
|---|--------|--------|---------|-------|
| F01 | Yarışma 2026-09-01 → 2026-10-11 23:59:59 CET | dc2026/index.html | 2026-09-01 | ✅ |
| F02 | Ödül ilk 3 takıma toplam 5000 EUR | dc2026/index.html | 2026-09-01 | ✅ |
| F03 | Sıralama = Ocak + Temmuz 2026 kalkışlarında RMSE | dc2026/index.html | 2026-09-01 | ✅ |
| F04 | Takım **en iyi** RMSE'siyle sıralanır (son değil, en iyi) | dc2026/ranking.html | 2026-09-01 | ✅ |
| F05 | **Yayınlanmış gönderim limiti YOK** | dc2026/ranking.html | 2026-09-01 | ⚠️ Discord'da teyit et |
| F06 | Sıralama sürecinden "öğrenme/sömürme" girişimleri izleniyor, haksız sayılıyor | dc2026/ranking.html | 2026-09-01 | ✅ |
| F07 | Gönderim adı `<takim>_v<N>.parquet`; kolonlar `MVT_ID_mvt` + `TAXITIME_SEC_mvt` | dc2026/ranking.html | 2026-09-01 | ✅ |
| F08 | Doğrulama: tüm MVT_ID eşleşmeli, eksik satır yok, fazla satır yok | dc2026/ranking.html | 2026-09-01 | ✅ |
| F09 | Takım formu **CANLI** → docs.google.com/forms/d/e/1FAIpQLScgRRk0j5Giot8puUAjzXC7ScR926Oupd62LbRVS1g8Y2p4hw | dc2026/index.html link | 2026-09-01 | ✅ (önceki "example.com" iddiası ❌) |
| F10 | Form 22 sayfa; katılımcı adlarının yayını **rızaya bağlı**; kurallara uyum onayı isteniyor | Form sayfa 1 | 2026-09-01 | ✅ |
| F11 | Form şartı: **2026 veri seti yarışma dışında, kamuya açılana kadar kullanılamaz** | Form sayfa 1 | 2026-09-01 | ✅ |
| F12 | EUROCONTROL / OpenSky Network mensupları katılabilir ama **ödüle hak kazanamaz** | Form sayfa 1 | 2026-09-01 | ✅ |
| F13 | Türkiye EUROCONTROL Üye Devleti (1989'dan beri) → katılım + ödül uygun | eurocontrol.int üye listesi | 2026-09-01 | ✅ |
| F14 | Ödül şartı: kod GitHub'da **GPLv3**, tüm dış veri seti açık lisanslı + belgeli, tekrar üretilebilir, özgün | dc2026/eligibility.html | 2026-09-01 | ✅ |
| F15 | Onay iki turlu: form → doğrulama e-postası → cevap → bucket anahtarları | dc2026/index.html | 2026-09-01 | ✅ |

## Veri seti

| # | Gerçek | Kaynak | Kontrol | Durum |
|---|--------|--------|---------|-------|
| D01 | 11 havalimanı: EDDF EDDM EGLL EHAM LEBL LEMD LFPG LIRF **LTAI LTFM** LSZH | dc2026/data.html | 2026-09-01 | ✅ |
| D02 | Eğitim: 12 aylık parquet, 2025 tam yıl, toplam ~277 MB | dc2026/data.html | 2026-09-01 | ✅ |
| D03 | `ranking.parquet` 27 MB (Ocak + Temmuz 2026); `submitting.parquet` 1.1 MB | dc2026/data.html | 2026-09-01 | ✅ |
| D04 | Toplam 4.167.797 hareket (ARR + DEP) | dc2026/data.html | 2026-09-01 | ✅ |
| D05 | Ranking'de **DEP için SADECE** `BLOCK_TIME_UTC_mvt` ve `TAXITIME_SEC_mvt` boşaltılmış | dc2026/data.html | 2026-09-01 | ✅ |
| D06 | `AOBT_3_flt` (M3 gerçek blok saati) **boşaltılanlar listesinde DEĞİL** | dc2026/data.html | 2026-09-01 | 🔴 **I0'da ölç: `MVT_TIME − AOBT_3` ne kadar iyi bir tahmin?** |
| D07 | `MVT_TIME_UTC_mvt` DEP'te boşaltılmamış = kalkış saati biliniyor | dc2026/data.html | 2026-09-01 | ✅ |
| D08 | `RUNWAY_mvt`, `STAND_mvt` boşaltılmamış | dc2026/data.html | 2026-09-01 | ✅ |
| D09 | ARR satırlarının hiçbir kolonu boşaltılmamış | dc2026/data.html | 2026-09-01 | ✅ |
| D10 | Uçuş (`*_flt`) kolonları yalnızca NM eşleşmesi varsa dolu (`FLIGHT_ID_mvt` "if matched") | dc2026/data.html | 2026-09-01 | ⏳ eşleşme oranını ölç |
| D11 | Askeri / Devlet Başkanı / hassas hareketler veri setinden çıkarılmış | dc2026/data.html | 2026-09-01 | ✅ |
| D12 | Organizatör uyarısı: hareket ve uçuş bilgileri arasında tutarsızlıklar var, uzlaştırılmamış | dc2026/data.html | 2026-09-01 | ✅ |
| D13 | `MVT_TIME_UTC_mvt` tanımı "(best available) movement time" — kaynağı/hassasiyeti belirsiz | dc2026/data.html | 2026-09-01 | ⏳ `MVT−BLOCK == TAXITIME` kimliği 2025'te tutuyor mu? |

## Alan bilgisi / metodoloji

| # | Gerçek | Kaynak | Kontrol | Durum |
|---|--------|--------|---------|-------|
| M01 | Yarışmanın amacı: **post-ops** analizde kısıtlı işletme aralıklarını bulmak + kısıtsız duruma göre fazladan yakıt/CO2 ölçmek | dc2026/rationale.html | 2026-09-01 | ✅ |
| M02 | Taxi-out seçilme gerekçesi: "elde etmesi zor ve doğru tahmin etmesi zor" | dc2026/rationale.html | 2026-09-01 | ✅ |
| M03 | Değişkenlik nedenleri: havayolu kısıtları, havalimanı prosedürleri/yükü, ATFM | dc2026/rationale.html | 2026-09-01 | ✅ |
| M04 | PRC resmî KPI: additional taxi-out = gerçek taxi-out − **her stand-pist kombinasyonu için** kestirilen referans süre | ansperformance.eu/definition/additional-taxi-out-time | 2026-09-01 | ✅ |
| M05 | Resmî metodoloji dokümanı: `library/ATXOT_indicator_documentation_mar23.pdf` (2023 revizyonu) | ansperformance.eu/methodology/additional-taxi-out-time | 2026-09-01 | ✅ indirildi → docs/reference/ |
| M06 | Resmî referans = **her (havalimanı, STAND, kalkış PİSTİ) kombosu için P10**, kayan 12 ay üzerinden | ATXOT s.14, §3.5 4b | 2026-09-01 | ✅ (önceki "P20" tahmini ❌) |
| M07 | Referans geçerlilik şartı: komboda **taxi-out ≤ P10 olan en az 10 uçuş** olmalı; yoksa referans atanmaz | ATXOT s.15, §3.5 | 2026-09-01 | ✅ |
| M08 | Resmî filtreler: taxi-out > 120 dk hariç, pist/stand/blok saati eksikse hariç, **helikopterler hariç**, **AOBT sonrası de-icing yapan uçuşlar hariç** | ATXOT s.13, §3.4 adım 1 | 2026-09-01 | ✅ |
| M09 | Resmî formül: `TaxiOut(f) = ATOT(f) - AOBT(f)` | ATXOT s.13, §3.4 adım 3 | 2026-09-01 | ✅ |
| M10 | PRC **uçak tipini/sınıfını gruplamada BİLEREK kullanmıyor** — örneklem küçülmesin diye; ama "taxi hızını etkileyebileceğini" kabul ediyor | ATXOT s.11, §3.2 | 2026-09-01 | ✅ **→ modelimizin kapattığı boşluk #1** |
| M11 | PRC'nin **dikkate almadığını açıkça yazdığı** faktörler: farklı taxi rotaları, uçak taxi hızı, özel olaylar (apron çalışması vb.) | ATXOT s.15, §5 | 2026-09-01 | ✅ **→ boşluk #2, makalenin katkı yüzeyi** |
| M12 | Push-back süresi ve kalkış koşusu pist işgal süresi "sistemik" sayılıp referansın içine gömülüyor | ATXOT s.10, §3.1 | 2026-09-01 | ✅ |
| M13 | **AOBT kaynağı yalnızca havalimanı APDF akışı** (alternatif kaynak yok); NM akışı sadece kalkış saatini tamamlamak için kullanılıyor | ATXOT s.17, Tablo 3 | 2026-09-01 | ✅ **→ `BLOCK_TIME_UTC_mvt` = APDF AOBT, `AOBT_3_flt` = NM M3 AOBT: aynı olayın FARKLI iki ölçümü, birebir aynı değil** |
| M14 | Zaman damgaları bazı kaynaklarda yalnızca HH:MM hassasiyetinde olabilir | ATXOT s.15, §4 | 2026-09-01 | ✅ |

## Onceki edisyonlar ve altyapi (2026-09-01 arastirmasi)

| # | Gerçek | Kaynak | Kontrol | Durum |
|---|--------|--------|---------|-------|
| P01 | Takim adlari **otomatik atanir** (adjective-noun): `resourceful-quiver`, `jubilant-vase`, `team_likable_jelly` | 2024+2025 GitHub org listeleri | 2026-09-01 | ✅ isim bizim kararimiz degil |
| P02 | Gonderim **MinIO bucket**'a yapiliyor: `mc ls opensky/prc-2025-<takim>/`, dosya `<takim>_v<N>.parquet` | resourceful-quiver/scripts/check_submission_ver.sh | 2026-09-01 | ✅ `mc.exe` kuruldu (~/bin) |
| P03 | 2025 birincisi (resourceful-quiver) **TU Delft Havacilik Fakultesi**; 2024 birincisi ENAC hocalari | PRC_2025_report.pdf, 2024 duyurusu | 2026-09-01 | ✅ alan akademik agirlikli |
| P04 | 2025 birincisi ablation'i **CV ile degil dogrudan sıralama seti (leaderboard) ile** yapmis; "k-fold'u rapordan cikardik, sıralama RMSE'si daha degerli" | PRC_2025_report.pdf §6 | 2026-09-01 | ✅ ~18 gonderimlik ablation → gercek limit yok |
| P05 | 2025'te en buyuk tekil kazanc **hedefin yeniden parametrelendirilmesiydi**: yakit tuketimi yerine yakit *akisi* ile egitim (RMSE 220.56 → 201.04), tum oznitelik gruplarindan buyuk | PRC_2025_report.pdf §6.3 | 2026-09-01 | ✅ **bizdeki karsiligi: ham taxi-out yerine P10 referansi uzerinden artik** |
| P06 | 2025 birincisinin makalesi 14 sayfa, JOAS on-baski formati: Abstract/Keywords/Abbreviations + Giris, Veri, On-isleme, Oznitelik, Model, Sonuclar, Vargi; katkinin sunumu **tek bir oznitelik x RMSE ablation tablosu** | PRC_2025_report.pdf | 2026-09-01 | ✅ sablon |
| P07 | 2026'da **yorunge (ADS-B) verisi YOK** — yalnizca hareket kayitlari. 2024/2025 ADS-B + OpenAP/aerodinamik uzmanligi gerektiriyordu | dc2026/data.html | 2026-09-01 | ✅ **havacilik-disi tabular ekipler icin saha duzlesti** |
| W01 | IEM ASOS/METAR 11 havalimaninin tamamini kapsiyor, 2025-01-01..2026-07-31 arasi 577 gunun hepsi, gunde 48 gozlem, eksik <%0,03 | kendi indirmemiz | 2026-09-01 | ✅ 306.222 satir indirildi |
| W02 | IEM verisi **kamu mali**, atif takdir ediliyor | mesonet.agron.iastate.edu/disclaimer.php | 2026-09-01 | ✅ odul sartini karsiliyor |
| W03 | Ocak 2026 de-icing kosulu orani: **LSZH %18,0 · EHAM %13,4 · EDDM %11,2 · LTFM %9,9 · EDDF %8,3**; LTAI/LEBL/LIRF **%0** | kendi METAR analizimiz | 2026-09-01 | ✅ **Ocak hatasi bu bes havalimaninda toplanacak; LTAI'de de-icing yok** |
| W04 | De-icing vekili mevsimsel saglamayi geciyor: 2025-01 %2,3 → 2026-07 %0,04 | kendi METAR analizimiz | 2026-09-01 | ✅ |
| A01 | `SCHED_TIME_UTC_mvt` siralama setinde **bosaltilmamis** → `MVT_TIME − SCHED_TIME = taxi_out + kalkis_gecikmesi` kimligi kullanilabilir | dc2026/data.html D05 + kendi turetmemiz | 2026-09-01 | ✅ ikinci mesru tutamak |
| A02 | Blok saatine **iki bagimsiz tutamak** var: NM'in `AOBT_3_flt` olcumu ve planlanan `SCHED_TIME`. Problemin cekirdegi bu ikisini uzlastirip artik belirsizligi modellemek | kendi analizimiz | 2026-09-01 | ⏳ ikisinin RMSE'si `probe_data.py` §5 ve §8'de olculecek |
| A03 | Indirgenemez belirsizligin buyuk kismi **kalkis gecikmesinin** (gercek blok − planlanan blok) dagiliminda; std'si taxi-out'un kendi std'siyle kiyaslanmali | kendi analizimiz | 2026-09-01 | ⏳ §8 |

## JOAS makalesi (2026-09-01 arastirmasi)

| # | Gerçek | Kaynak | Kontrol | Durum |
|---|--------|--------|---------|-------|
| J01 | **LaTeX zorunlu**, Word reddediliyor; sablon `github.com/open-aviation/joas-template` | joas/about/submissions | 2026-09-01 | ✅ sablon repoya alindi |
| J02 | Tum icerik **tek `main.tex`** dosyasinda; `\input{}`/`\include{}` yasak; dosya adlari degistirilemez | joas-template/main.tex | 2026-09-01 | ✅ |
| J03 | Ozet **tek paragraf ≤300 kelime**, dort ogeyi icermeli (amac, tasarim, bulgular, yorum); baslik ≤12 kelime | joas-template/main.tex | 2026-09-01 | ✅ |
| J04 | **Open data statement** ve **Reproducibility statement** ZORUNLU bolumler | joas-template/main.tex | 2026-09-01 | ✅ iskelette var |
| J05 | Kisaltma ancak metinde **10'dan fazla** geciyorsa tanimlanir; tablolar basit `tabular` olmali (ozel tasarim HTML surumunu bozuyor) | joas-template/main.tex | 2026-09-01 | ✅ |
| J06 | Gonderim: derlenmis PDF + LaTeX kaynaginin ZIP'i. Hakemlik **acik** (kimlikler paylasilir, degerlendirmeler yayimlanir). Ucret yok | joas/about/submissions | 2026-09-01 | ✅ |
| J07 | Makale turu: `manuscript=article` (Research Article, General). "Open Software Focus" yazarin yazilimin ana gelistiricisi olmasini ve odagin yazilim olmasini istiyor — bizim katkimiz yontem | joas/about/submissions | 2026-09-01 | ✅ karar verildi |

## EUROCONTROL resmi gostergesi ve de-icing (2026-09-01 analizi)

| # | Gerçek | Kaynak | Kontrol | Durum |
|---|--------|--------|---------|-------|
| E01 | Resmi ATXOT gostergesi acik indirilebilir: havalimani-ay bazinda referans ve ek taxi-out suresi, 2018-2026 | eurocontrol.int/performance/data/download/xls/Taxi-Out_Additional_Time.xlsx | 2026-09-01 | ✅ indirildi |
| E02 | **2025 ortalama toplam taxi-out (dk/kalkis):** EGLL 22,7 · LIRF 19,0 · LTFM 16,9 · LEMD 16,8 · LEBL 15,8 · EDDF 14,2 · EHAM 13,0 · EDDM 12,9 · LSZH 11,9 | resmi gosterge | 2026-09-01 | ✅ **hedefin olcegi: ~715-1365 sn** |
| E03 | **LTAI resmi gostergede HIC yok** (24 ay, TF=0) — Antalya EUROCONTROL performans semasinda degil | resmi gosterge | 2026-09-01 | ✅ dis dogrulama kaynagi yok; veri kalitesi farkli olabilir |
| E04 | Gosterge Haziran 2026'da bitiyor → **Temmuz 2026 kapsanmiyor**, ozellik olarak kullanilamaz | resmi gosterge META | 2026-09-01 | ✅ yalnizca dogrulama |
| E05 | METAR de-icing vekilimiz resmi "referanssiz ucus orani" ile **r = 0,757** korele; havalimani icinde LTFM 0,98 · LSZH 0,97 · EDDF 0,94 · EDDM 0,94 · LFPG 0,87 | kendi analizimiz | 2026-09-01 | ✅ vekil bagimsiz dogrulandi |
| E06 | **Havalimanlarinin de-icing rejimi farkli.** EHAM: referanssiz oran yil boyu sabit ~%1 ama ek sure kisin +1,46 dk. EDDM/LSZH: kisin ucuslarin buyuk kismi gostergeden dusuyor (EDDM Ocak 2026 %31), ek sure artmiyor | kendi analizimiz | 2026-09-01 | ✅ **Ocak hatasi EDDM/LSZH'de resmi gostergenin ATTIGI ucuslarda toplanacak** |
| E07 | Ek taxi-out suresi **her havalimaninda** kisin yazdan dusuk (yaz trafik zirvesi); EHAM tek istisna | kendi analizimiz | 2026-09-01 | ✅ EHAM anomalisini guclendiriyor |

## Olcek ve performans (2026-09-01 olcumu)

| # | Gerçek | Kaynak | Kontrol | Durum |
|---|--------|--------|---------|-------|
| S01 | Gercek olcekte (4,17M hareket) uctan uca dogrulama kosusu **96 sn**, tepe bellek **5,15 GB / 15,9** | kendi olcumumuz, sentetik veri | 2026-09-01 | ✅ ADR-0002 |
| S02 | Gonderim yolu (en yuksek bellek noktasi) **171 sn**, tepe **7,06 GB** | kendi olcumumuz | 2026-09-01 | ✅ out-of-core gerekmiyor |
| S03 | 4,17M hareketin **2,08M'i kalkis**; 114 ham kolon, 95 modellenebilir oznitelik | kendi olcumumuz | 2026-09-01 | ⏳ gercek veride dogrulanacak |
| S04 | Tam ablation (13 yapilandirma x 1500 tur) tahmini **~1,7 saat**, 5 tohumla ~8,5 saat | S01'den olcekleme | 2026-09-01 | ✅ gece kosusu planlanabilir |

| O01 | OPDI (PRC + OpenSky acik girisimi) ADS-B'den turetilmis ucus olaylari yayimliyor; v0.0.2'de **park pozisyonu giris/cikis** var, kapsam 2022-01 → 2026-08-08 (her iki siralama ayi da) | opdi.aero/flight-event-data.html | 2026-09-01 | ✅ |
| O02 | **Park pozisyonu olaylari yalnizca LSZH ve EDDF'te var**; EHAM/LIRF/LTAI/LTFM'de **sifir**. Sebep: OPDI bu olaylari OSM park pozisyonu poligonlarindan turetiyor, o poligonlar cogu havalimaninda yok | kendi olcumumuz, 10 gunluk dosya | 2026-09-01 | ✅ **ELENDI** (docs/opdi_negative_result.md) |
| O03 | **LTFM ve LTAI'de acik ADS-B yer kapsamasi neredeyse sifir** (10 gunde 25 ve 119 pist girisi) — ADS-B tabanli her yaklasim tam da iki Turk havalimaninda cokerdi | kendi olcumumuz | 2026-09-01 | ✅ |

## Takım onaylandı (2026-09-01 13:45)

| # | Gerçek | Kaynak | Kontrol | Durum |
|---|--------|--------|---------|-------|
| T01 | **Takım adı: `vibrant-lollipop`** (otomatik atandi, P01 dogrulandi) | hello-noreply@opensky-network.org | 2026-09-01 | ✅ |
| T02 | **Gonderim bucket'i: `prc-2026-vibrant-lollipop`** | ayni e-posta | 2026-09-01 | ✅ |
| T03 | Gonderim dosya adi: `vibrant-lollipop_vN.parquet` | ayni e-posta | 2026-09-01 | ✅ `submission.py` deseniyle uyumlu |
| T04 | Giris **SSO ile**: konsolda "Other Authentication Methods" → "Login with SSO" → Keycloak → OpenSky kimlik bilgileri | ayni e-posta | 2026-09-01 | ✅ |
| T05 | Gonderimden kisa sure sonra bucket'ta bir **sonuc dosyasi** olusuyor → her gonderim icin geri bildirim var | ayni e-posta | 2026-09-01 | ✅ leaderboard beklemeye gerek yok |
| T06 | 2024'te uc nokta `https://s3.opensky-network.org/`, alias `mc alias set dc24 <uc> ACCESS SECRET` | dc2024/data.html | 2026-09-01 | ⏳ 2026 konsol URL'si e-postadaki baglantida |
| T07 | Iletisim: Discord "PRC Data Challenge 2026" sunucusu, challenge@opensky-network.org | ayni e-posta | 2026-09-01 | ✅ |
| T08 | **Cloudflare WARP acikken OSN'ye erisilemiyor** (DNS'i WARP yonetiyor, TLS kesiliyor); Discord ise WARP'siz engelli | kendi teshisimiz | 2026-09-01 | ✅ ikisi ayni anda calismiyor |

## GERCEK VERI (2026-09-01, indirildi ve olculdu)

| # | Gerçek | Kaynak | Kontrol | Durum |
|---|--------|--------|---------|-------|
| R01 | **Veri setinde 10 havalimani var, 11 degil. LTAI (Antalya) YOK.** Ne egitimde ne siralamada tek satiri var | kendi olcumumuz | 2026-09-01 | ✅ **yarisma sayfasi 11 diyor, veri 10** (E03 ile tutarli: LTAI performans semasinda degil) |
| R02 | **`ADEP_mvt` hareketin havalimani DEGIL, ucusun kalkis havalimani.** Hareket havalimani = DEP ise `ADEP_mvt`, ARR ise `ADES_mvt`. Egitimde 1.582 farkli `ADEP_mvt` var | kendi olcumumuz | 2026-09-01 | 🔴 **kodda hata: varis turevli tum oznitelikler yanlis havalimaninda gruplaniyordu** |
| R03 | **Siralama setinde Temmuz'da yalnizca 3 havalimani var: EDDF, EGLL, EHAM.** Ocak'ta 10'unun hepsi | kendi olcumumuz | 2026-09-01 | 🔴 **dogrulama semasi bunu yansitmali** |
| R04 | Siralama seti: Ocak 152.719 kalkis (10 apt) + Temmuz 63.157 kalkis (3 apt) = **215.876**. Ocak toplam satirlarin **%71'i** | kendi olcumumuz | 2026-09-01 | ✅ RMSE'yi Ocak domine ediyor |
| R05 | Egitim tam **4.167.797** hareket (yayimlanan sayiyla birebir), 2.085.047'si kalkis | kendi olcumumuz | 2026-09-01 | ✅ |
| R06 | Kimlik `MVT_TIME − BLOCK_TIME == TAXITIME` **tam tutuyor** (oran 1,0000, azami sapma 0 sn) | probe §2 | 2026-09-01 | ✅ TAXITIME turetilmis, zaman damgalari tutarli |
| R07 | Zaman damgalari **saniye hassasiyetinde** (saniyesi sifir olan oran %1,6-%8,4) — HH:MM sorunu YOK | probe §3 | 2026-09-01 | ✅ M14 endisesi gecersiz |
| R08 | **`AOBT_3_flt` siralama setinde %98,52 dolu**; naif `MVT − AOBT_3` tahmincisi **RMSE 384,9 sn** (MAE 238, medyan mutlak hata 175, yanlilik +17) | probe §5 | 2026-09-01 | ✅ **cozum degil, guclu ozellik** (kendi esigim >200 sn idi) |
| R09 | Naif AOBT_3 havalimani bazinda: EDDF 255 · LSZH 268 · LEMD 276 · LEBL 311 · EHAM 330 · EDDM 349 · LFPG 380 · EGLL 419 · **LTFM 531 · LIRF 557** | probe §5 | 2026-09-01 | ✅ LTFM ve LIRF en zor |
| R10 | **Hedef olcegi yayimlanan gostergeyle birebir ortusuyor:** EGLL ort 1364 sn (22,7 dk), LSZH 740 sn (12,3 dk) — E02'de resmi seri 22,7 ve 11,9 dk demisti | probe §6 | 2026-09-01 | ✅ dis veri calismasi dogrulandi |
| R11 | **LIRF uc deger yuvasi:** std 1332 sn, p99 4019 sn, %0,30'u 120 dakikayi asiyor. LSZH'de %0,22 **negatif** taxi suresi var | probe §6 | 2026-09-01 | ✅ kirpma degil modelleme karari |
| R12 | En yuksek varyansli aylar **Temmuz (std 745) ve Ocak (605)** — siralama aylari en zor iki ay | probe §6 | 2026-09-01 | ✅ |
| R13 | Kombo (apt, stand, pist) ortalamasi taban modeli: **RMSE 628,4 sn**; havalimani ortalamasi 660,0; genel ortalama 686,6 | probe §7 | 2026-09-01 | ✅ ilk gonderim seviyesi |
| R14 | Soguk baslangic dusuk: siralama kombolarinin **%99,46'si** egitimde gorulmus; stand/pist bos oran 0 | probe §7 | 2026-09-01 | ✅ |
| R15 | Kalkis gecikmesi (gercek blok − planlanan) std **2238 sn**, %24,2'si erken. `MVT − SCHED` naif tahmincisi RMSE **2412,7** | probe §8 | 2026-09-01 | ✅ SCHED, AOBT_3'ten cok daha zayif tutamak |

## Board (gonderim sonuclari)

| # | Gerçek | Kaynak | Kontrol | Durum |
|---|--------|--------|---------|-------|
| B01 | **v1 board skoru: RMSE 331,2256**, status Succeeded, 215.876 ciftin tamami kullanildi | bucket `vibrant-lollipop_v1.parquet_result.json` | 2026-09-01 | ✅ ilk taban |
| B02 | Gonderim sonrasi bucket'a **iki dosya** dusuyor: `<ad>_result.json` (skor) ve `<ad>_persist.json` (durum). Sonuc ~15 saniyede geliyor | ayni | 2026-09-01 | ✅ hizli geri bildirim, leaderboard beklemeye gerek yok |
| B03 | Gercek hedef `prc-2026-testsets/truthing.parquet`'te tutuluyor (bize kapali) | result.json `inputs` alani | 2026-09-01 | ✅ |
| B04 | **Yerel dogrulama board'dan KOTUMSER:** yerel 378,80 → board 331,23 (%12,6 daha iyi). Guvenli yon; yerel iyilesme board'a gecerse gecer | kendi olcumumuz | 2026-09-01 | ⏳ ikinci gonderimde iliski dogrulanacak |
| B05 | **Canli lider tablosu REST API'de:** `https://datacomp.opensky-network.org/api/competitions/bb3693e1-26bc-4a9e-8619-4fe78b4eab0c/leaderboard` — sayfada tablo gorunmuyor, Observable ile gomulu. `scripts/leaderboard.py` ceker | dc2026/ranking.html icinden cikarildi | 2026-09-01 | ✅ |
| B06 | **32 takim kayitli**, hepsi 2026-09-01'de. `vibrant-lollipop` Turkiye olarak listede | dc2026/teams.html | 2026-09-01 | ✅ |
| B07 | 2026-09-01 15:35 durumu: **yalnizca 2 takim gonderim yapmis.** enthusiastic-daisy 304,98 (v2) · **vibrant-lollipop 331,23 (v1)** · enthusiastic-daisy 485,23 (v1) | leaderboard API | 2026-09-01 | ✅ lidere fark 26,25 |

## Açık sorular

| # | Soru | Nasıl kapanır |
|---|------|---------------|
| Q01 | Günlük/toplam gönderim limiti var mı? | Discord'da sor. P04 dolaylı kanıt: 2025 birincisi ~18 gönderimlik ablation yapmış, sıkı bir limit yok görünüyor |
| Q02 | ~~`AOBT_3_flt` ne kadar iyi?~~ | **KAPANDI (R08):** %98,52 dolu, naif RMSE 384,9 sn. Guclu ozellik, cozum degil |
| Q03 | ~~Leaderboard canlı mı?~~ | **KAPANDI (B02, B05):** skor ~15 sn içinde bucket'a JSON olarak düşüyor; sıralama REST API'de |
| Q04 | ~~Takım adı ne olacak?~~ | **KAPANDI:** `vibrant-lollipop` atandı (T01) |
