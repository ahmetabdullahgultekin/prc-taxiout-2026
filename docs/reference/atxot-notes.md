# EUROCONTROL Resmi Taxi-Out Metodolojisi — Damitilmis Notlar

Kaynak: `ATXOT_indicator_documentation_mar23.pdf`, Edition 01.00, 16-03-2023, EUROCONTROL EGSD/AIU/OPS.
Tam metin: `ATXOT_methodology.txt`. Sayfa numaralari PDF sayfasidir.

Bu, **yarismayi duzenleyen kurumun kendi gostergesinin resmi tanimidir.** Modelimizin referans
bileseni bunu birebir yeniden uretmeli; katkimiz kurumun kendi yazdigi bosluklari kapatmaktan gelir.

## Resmi tanim

```
TaxiOut(f)            = ATOT(f) - AOBT(f)                       (s.13, adim 3)
Reference(combo)      = P10( TaxiOut times in combo )           (s.14, adim 4b)
Additional(f, combo)  = TaxiOut(f) - Reference(combo)           (s.13, adim 5)
```

- **combo = (havalimani, kalkis STAND, kalkis PISTI).** Baska hicbir degisken yok.
- Referans ornegi: **kayan 12 ay**, yerel saatle kalkis zamanina gore secilir (s.13, adim 2).
- **Gecerlilik sarti:** komboda taxi-out suresi P10'a esit veya daha kisa olan **en az 10 ucus**
  bulunmali. Saglanmazsa o komboya referans atanmaz ve o ucuslar gostergeden **tamamen dusurulur** (s.15).

## Resmi filtreler (s.13, adim 1)

Asagidakiler hesaptan cikarilir:
- taxi-out suresi **> 120 dakika**
- pist bilgisi, stand bilgisi veya blok saati eksik olanlar
- **helikopterler**
- **AOBT sonrasi (yani taxi sirasinda) de-icing yapan ucuslar**

Not: son madde onemli. PRC de-icing'li ucuslari gostergeden atiyor cunku bunlar
"engelsiz" varsayimini bozuyor. Bizim hedefimiz ise ham taxi-out — **de-icing satirlarini
atamayiz, modellemek zorundayiz.** Ocak 2026 hatasinin buyuk kismi burada olacak.

## PRC'nin BILEREK dikkate almadiklari — bizim katki yuzeyimiz

| Faktor | PRC'nin gerekcesi | Bizim durumumuz |
|--------|-------------------|-----------------|
| **Ucak tipi / agirlik sinifi** (s.11, §3.2) | "taxi hizini etkileyebilir" ama gruplamaya eklenirse ornek boyutu duser | GBDT'de ornek boyutu sorunu yok — dogrudan ozellik olarak girer |
| **Taxi rotasi** (s.15, §5) | Veride rota yok | Bizde de yok; stand-pist ciftiyle vekillenir |
| **Taxi hizi** (s.15, §5) | Veride hiz yok | Ucak tipi + operator ile kismen vekillenir |
| **Ozel olaylar** (apron calismasi vb.) | Ozel ornek gerektirir | Zaman-trendi ve havalimani x ay etkilesimi ile kismen yakalanir |
| **Kuyruk** | Zaten olculen buyukluk (additional time = kuyruk) | Bizim hedefimiz toplam sure — kuyrugu **acikca modelleyecegiz** |

PRC ayrica push-back suresini ve kalkis kosusu pist isgal suresini "sistemik" sayip
referansin icine gomuyor (s.10, §3.1).

## Veri kaynagi — hedef sizinti sorusu icin kritik

Tablo 3 (s.17):

| Buyukluk | Ana kaynak | Alternatif kaynak |
|----------|-----------|-------------------|
| Gercek kalkis saati (ATOT) | Havalimani (APDF) | ANSP **veya Network Manager** |
| **Gercek blok saati (AOBT)** | **Havalimani (APDF)** | **yok** |
| Kalkis pisti / standi | Havalimani (APDF) | yok |

Cikarim: yarisma verisindeki `BLOCK_TIME_UTC_mvt` APDF kaynakli AOBT'dir; `AOBT_3_flt` ise
**Network Manager M3 yorungesinin** blok saatidir. Ayni fiziksel olayin **iki farkli olcumu** —
korele ama ozdes degil. Bu bir sizinti degil, gercek operasyonel durumun yansimasi:
NM her ucus icin kestirim tutar, APDF ise yalnizca veri paylasan havalimanlarinda vardir.

**Olculecek (Q02):** 2025 verisinde `MVT_TIME_UTC_mvt - AOBT_3_flt` ile gercek `TAXITIME_SEC_mvt`
arasindaki RMSE nedir? Bu sayi yarismanin zorluk tabanini belirler.

## Kalite uyarisi

Zaman damgalari bazi kaynaklarda yalnizca **HH:MM** hassasiyetinde olabilir (s.15, §4);
saniye alani her zaman anlamli degil. `probe_data.py` bunu havalimani bazinda olcer.
