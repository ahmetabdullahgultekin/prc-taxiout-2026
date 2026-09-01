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

## Açık sorular

| # | Soru | Nasıl kapanır |
|---|------|---------------|
| Q01 | Günlük/toplam gönderim limiti var mı? | Discord'da sor. P04 dolaylı kanıt: 2025 birincisi ~18 gönderimlik ablation yapmış, sıkı bir limit yok görünüyor |
| Q02 | `AOBT_3_flt` ranking.parquet'te dolu mu, doluysa ne kadar iyi? | Veri iner inmez `scripts/probe_ranking.py` |
| Q03 | Leaderboard canlı mı, skor ne zaman görünüyor? | İlk gönderimde ölç |
| Q04 | ~~Takım adı ne olacak?~~ | **KAPANDI (P01):** otomatik atanıyor |
