# JOAS makalesi — kurallar ve plan

Kaynak: <https://journals.open.tudelft.nl/joas/about/submissions> ve
<https://github.com/open-aviation/joas-template> (ikisi de 2026-09-01'de okundu).

Yarışma sayfası, özellikle üst sıradaki takımları JOAS'a makale göndermeye **güçlü
biçimde** teşvik ediyor. 2025 jürisi birinciyi seçerken "JOAS formatına neredeyse
tamamlanmış bir makale" sunmasını açık bir üstünlük saydı. Bu yüzden makale son haftaya
bırakılan bir ek değil, teslimin parçası.

## Sert kurallar (ihlali doğrudan reddettiriyor)

| Kural | Not |
|---|---|
| **LaTeX zorunlu** | Word kabul edilmiyor |
| **Tek dosya `main.tex`** | `\input{}` / `\include{}` yasak |
| **Dosya adları sabit** | `main.tex`, `figures/`, `reference.bib` yeniden adlandırılamaz |
| **LaTeX hatasız derlenmeli** | Şablon bunu kırmızıyla yazıyor |
| Başlık ≤ 12 kelime, Title Case | Kısaltma kullanma |
| Özet tek paragraf, ≤ 300 kelime | Dört öge zorunlu: amaç, tasarım, bulgular, yorum |
| Kısaltma ancak >10 kez geçiyorsa | Yoksa açık yaz |
| Tablolar **basit `tabular`** | Özel tasarım HTML sürümünü bozuyor |
| Şekiller `figures/` içinde, `.png`/`.pdf` | Küçük harf, boşluksuz ad |
| Metinde `Figure \ref{}` | `Fig.` yazma |
| **Open data statement** | ZORUNLU bölüm |
| **Reproducibility statement** | ZORUNLU bölüm |
| Author contributions (CRediT) | Yalnızca birden fazla yazar varsa |

Gönderim iki dosya: derlenmiş PDF + LaTeX kaynağının ZIP'i.
Hakemlik **açık**: hakem ve yazar kimlikleri paylaşılıyor, değerlendirmeler yayımlanıyor.
Ücret yok.

## Makale türü seçimi

`manuscript=article` (Research Article, General) doğru seçim. Alternatifler:

- **Open Software Focus**: yazarın yazılımın ana geliştiricisi olması gerekiyor ve odak
  yazılımın kendisi olmalı. Bizim katkımız yöntem, kütüphane değil — uygun değil.
- **Open Data Focus**: veri kümesini biz derlemiyoruz — uygun değil.

## Yazma sırası (sayılar geldikten sonra)

1. **Method** — kod zaten yazıldığı için en kolayı, ve en çok gerekçe barındıran bölüm.
2. **Data** — probe raporundan doğrudan beslenir.
3. **Results** — `run_ablation.py` çıktısı zaten markdown tablo; LaTeX'e çevrilecek.
4. **Related Work** — `docs/literature.md`'den; **tam metni okunmamış alıntılar
   temizlenecek** (o dosyanın son bölümünde listeli).
5. **Discussion** — negatif sonuçlar burada, açıkça. 2025'te bir takım tam bunu yaptığı
   için övüldü.
6. **Introduction** ve **Abstract** — en son.

## Şekil adayları

| Dosya | İçerik | Kaynak |
|---|---|---|
| `taxiout_dagilimi.png` | Havalimanı bazında taxi-out dağılımı | probe §6 |
| `referans_kapsami.png` | ATXOT resmî seviye vs geri düşüş oranı | `reference.official_coverage` |
| `ablation.png` | Öznitelik ailesi katkıları | `run_ablation.py` |
| `retro_vs_nedensel.png` | İki çıpanın havalimanı bazında farkı | iki koşunun karşılaştırması |
| `deicing_ocak.png` | Ocak de-icing maruziyeti (LSZH %18 → LTAI %0) | METAR analizi |

Şekil üreten kod repoda olmalı — tekrar üretilebilirlik beyanı bunu istiyor.

## Derleme

```bash
cd docs/paper && make        # sablonun kendi Makefile'i (latexmk)
```

`make` bu makinede kurulu değil; TeX kurulumu gerekiyorsa Overleaf'e yüklemek en hızlısı
(şablon Overleaf'te de yayımlı).
