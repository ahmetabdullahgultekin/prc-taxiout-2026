# Dis Veri Setleri

**Odul uygunlugu sarti:** kullanilan tum ek veri setleri acik erisimli/acik lisansli ve belgelenmis olmali
(dc2026/eligibility.html). Bu dosya o belgelemedir. Bir veri kaynagi eklerken **once burayi doldur.**

| Kaynak | Ne icin | Erisim URL | Lisans | Eklendigi tarih |
|--------|---------|------------|--------|-----------------|
| EUROCONTROL ATXOT metodoloji dokumani | Resmi referans taxi-out tanimi (P10 / stand-pist) | https://ansperformance.eu/library/ATXOT_indicator_documentation_mar23.pdf | EUROCONTROL kamuya acik yayin | 2026-09-01 |
| Iowa Environmental Mesonet (IEM) ASOS/METAR arsivi | Sicaklik, cig noktasi, gorus, ruzgar, yagis, mevcut-hava kodlari; **de-icing vekili** | https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py | **Kamu mali** | 2026-09-01 |
| OurAirports (airports.csv, runways.csv) | Havalimani koordinatlari (kalkis kerterizi / departure-fix vekili), pist sayisi ve uzunluklari | https://davidmegginson.github.io/ourairports-data/ | **Kamu mali** | 2026-09-01 |
| EUROCONTROL Taxi-Out Additional Time gostergesi | **Yalnizca dogrulama**: ATXOT yeniden uygulamamizin ve METAR de-icing vekilinin bagimsiz kontrolu | https://www.eurocontrol.int/performance/data/download/xls/Taxi-Out_Additional_Time.xlsx | EUROCONTROL kamuya acik yayin | 2026-09-01 |

## Aday kaynaklar (henuz kullanilmadi)

| Kaynak | Ne icin | Lisans | Durum |
|--------|---------|--------|-------|
| OpenStreetMap (aeroway=taxiway/parking_position) | Seyrek (stand, pist) hucreleri icin gerilemeli mesafe; pist gecisi bayragi | ODbL | Dusuk oncelik — ampirik P10 muhtemelen daha iyi |

## IEM lisans metni (birebir)

> "The materials found on this website are in the public domain and may be used freely
> by anyone for any lawful purpose. Attributing the Iowa Environmental Mesonet of Iowa
> State University would be appreciated."
> -- https://mesonet.agron.iastate.edu/disclaimer.php (2026-09-01)

Feragatname: "we provide this information without any warranty of accuracy."
Atif JOAS makalesinde ve README'de verilecek.

## Indirilen METAR verisi

- Cekim: `python -m taxiout.adapters.metar_iem --start 2025-01-01 --end 2026-08-01`
- 11 havalimani x 2025-01-01..2026-07-31 = **306.222 gozlem**, havalimani basina gunde 48 (yarim saatlik)
- Eksik sicaklik/gorus orani <%0,03; tum havalimanlarinda 577 gunun tamami kapsanmis
- `report_type` parametresi **bilerek gonderilmiyor**: filtrelemek Avrupa'nin yarim saatlik
  yayinini saatlige dusuruyor ve kosullar aniden degistiginde yayinlanan SPECI raporlarini atiyor

## OurAirports lisans metni (birebir)

> "All data is released to the Public Domain, and comes with no guarantee of accuracy
> or fitness for use." … "We'd love you to give us credit, like we give credit to our
> sources, but you're not required to."
> -- https://ourairports.com/data/ (2026-09-01)

Atif zorunlu degil; yine de makalede ve README'de verilecek.

## Indirilen havalimani verisi

- 86.013 havalimani koordinati (varis noktasi dunyanin herhangi bir yerinde olabilir,
  kerteriz icin hepsi gerekli) + 11 yarisma havalimaninin acik pist ozeti.
- Pist sayilari: EHAM 6 · LTFM 6 · LFPG 5 · LEMD 4 · EDDF 4 · LSZH 4 · LIRF 3 · LTAI 3
  · LEBL 3 · **EDDM 2 · EGLL 2**. En kisitli iki havalimani EDDM ve EGLL.

## EUROCONTROL gostergesi — neden ozellik degil, dogrulama

Seri **aylik** ve yayimi yaklasik iki ay gecikmeli: 2026-09-01 itibariyla Haziran
2026'da bitiyor. Siralama aylarindan **Temmuz 2026 kapsanmiyor**, dolayisiyla ozellik
olarak kullanilamaz. Ayrica ayni temel veriden turetildigi icin ozellik olarak
kullanilmasi dairesel olurdu.

Dogrulama degeri yuksek: `scripts/analyse_deicing.py` METAR de-icing vekilimizi bu
serinin "gecerli referansi olmayan ucus orani" alanina karsi olcuyor (genel r = 0,757;
soguk havalimanlarinda 0,87-0,98). Sonuclar `docs/deicing_analysis.md`.

**LTAI resmi gostergede hic yok** (24 ay boyunca TF = 0): Antalya EUROCONTROL
performans semasinda degil.
