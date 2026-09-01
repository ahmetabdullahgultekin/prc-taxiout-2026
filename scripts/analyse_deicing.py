"""De-icing rejimi analizi: METAR vekilini resmi gostergeye karsi dogrular.

**Yarisma verisi gerektirmez.** Iki acik kaynak kullanir: METAR (Iowa State IEM,
kamu mali) ve EUROCONTROL'un yayimladigi Taxi-Out Additional Time gostergesi.

Sordugu soru: METAR'dan turettigimiz de-icing vekili gercekten de-icing'i mi olcuyor?
Bagimsiz bir olcum gerekiyordu; resmi gosterge onu sagliyor. PRC kendi gostergesinde
**AOBT sonrasi de-icing yapan ucuslari hesaptan atiyor** (ATXOT s.13 adim 1), yani
"gecerli referansi olmayan ucus orani" alani kis aylarinda de-icing'i tasiyor.

Bulunan sey bundan fazlasi: havalimanlarinin **de-icing rejimi farkli**, ve bu bizim
Ocak hatamizin nerede toplanacagini belirliyor. Ayrinti `docs/deicing_analysis.md`.

    python scripts/analyse_deicing.py --raw-dir D:/prc-taxiout-2026/00_raw
"""

from __future__ import annotations

import argparse
from pathlib import Path

import polars as pl

from taxiout.adapters import eurocontrol

OUT_MD = Path("docs/deicing_analysis.md")


def monthly_metar(metar: pl.DataFrame) -> pl.DataFrame:
    return metar.group_by(
        apt=pl.col("station"),
        yil=pl.col("valid").dt.year(),
        ay=pl.col("valid").dt.month(),
    ).agg(
        deicing=pl.col("deicing_vekili").mean(),
        kar=pl.col("kar").mean(),
        donma=pl.col("donma_yagisi").mean(),
        min_sicaklik=pl.col("sicaklik_c").min(),
    )


def table(df: pl.DataFrame, digits: dict[str, int] | None = None) -> str:
    digits = digits or {}
    lines = ["| " + " | ".join(df.columns) + " |",
             "|" + "|".join("---" for _ in df.columns) + "|"]
    for row in df.iter_rows():
        cells = []
        for col, v in zip(df.columns, row, strict=True):
            if v is None:
                cells.append("—")
            elif isinstance(v, float):
                cells.append(f"{v:.{digits.get(col, 3)}f}")
            else:
                cells.append(f"{v:,}" if isinstance(v, int) else str(v))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw-dir", required=True)
    args = ap.parse_args()
    raw = Path(args.raw_dir)

    metar_path = raw / "metar.parquet"
    if not metar_path.exists():
        raise SystemExit(
            f"METAR bulunamadi: {metar_path}\n"
            "once: python -m taxiout.adapters.metar_iem --start 2025-01-01 "
            "--end 2026-08-01 --out <yol>"
        )
    met = monthly_metar(pl.read_parquet(metar_path))
    off = eurocontrol.official_taxiout(raw)
    j = off.join(met, on=["apt", "yil", "ay"], how="inner").sort("apt", "yil", "ay")

    genel_ref = j.select(pl.corr("deicing", "referanssiz_oran")).item()
    genel_sure = j.select(pl.corr("deicing", "ek_sure_dk")).item()

    per = (
        j.group_by("apt")
        .agg(
            ay_sayisi=pl.len(),
            r_referanssiz=pl.corr("deicing", "referanssiz_oran"),
            r_ek_sure=pl.corr("deicing", "ek_sure_dk"),
            ort_deicing=pl.col("deicing").mean(),
            ort_referanssiz=pl.col("referanssiz_oran").mean(),
            kis_ek_sure=pl.col("ek_sure_dk").filter(pl.col("ay").is_in([1, 2, 12])).mean(),
            yaz_ek_sure=pl.col("ek_sure_dk").filter(pl.col("ay").is_in([6, 7, 8])).mean(),
        )
        .with_columns(kis_yaz_farki=pl.col("kis_ek_sure") - pl.col("yaz_ek_sure"))
        .sort("r_referanssiz", descending=True)
    )

    eksik = set(eurocontrol.CHALLENGE_AIRPORTS) - set(off["apt"].unique().to_list())

    # tablolar f-string DISINDA kurulur: f-string ifadesi icinde sozluk yazilamaz
    tablo_korelasyon = table(
        per.select("apt", "ay_sayisi", "r_referanssiz", "r_ek_sure", "ort_deicing",
                   "ort_referanssiz")
    )
    tablo_rejim = table(
        per.select("apt", "r_ek_sure", "kis_ek_sure", "yaz_ek_sure", "kis_yaz_farki"),
        digits={"kis_ek_sure": 2, "yaz_ek_sure": 2, "kis_yaz_farki": 2},
    )
    kapsam_disi = (
        "Resmi gostergede **hic verisi olmayan** havalimani: " + ", ".join(sorted(eksik))
        if eksik
        else "Tum yarisma havalimanlari gostergede kapsanmis."
    )

    body = f"""# De-icing rejimi: METAR vekilinin bagimsiz dogrulanmasi

Uretildigi komut: `python scripts/analyse_deicing.py --raw-dir <yol>`
**Yarisma verisi kullanilmaz** — iki acik kaynak: IEM METAR ve EUROCONTROL'un
yayimladigi Taxi-Out Additional Time gostergesi. Kapsam: {j.height} havalimani-ay.

## Neden bu karsilastirma anlamli

PRC resmi gostergesinde **AOBT sonrasi de-icing yapan ucuslari hesaptan atiyor**
(ATXOT s.13, adim 1). Dolayisiyla gostergenin "gecerli referansi olmayan ucus orani"
alani, kis aylarinda buyuk olcude de-icing'i tasir. Bu, METAR'dan turettigimiz
`deicing_vekili` alani icin **bagimsiz** bir olcumdur.

## Sonuc: vekil calisiyor

Tum veri uzerinde korelasyon **r = {genel_ref:.3f}** (de-icing vekili ↔ referanssiz
ucus orani). Havalimani icinde, aylar arasinda:

{tablo_korelasyon}

Soguk havalimanlarinda korelasyon 0.87–0.98; sicak olanlarda (LIRF, LEBL, EGLL)
de-icing neredeyse hic olmadigi icin korelasyon gurultudur, dusuk olmasi beklenir.

## Asil bulgu: havalimanlarinin de-icing rejimi farkli

De-icing vekili ile **ek taxi-out suresi** arasindaki korelasyon genelde
{genel_sure:+.3f}, yani neredeyse yok — ama havalimani bazinda tablo ikiye ayriliyor:

{tablo_rejim}

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

{kapsam_disi}
Antalya EUROCONTROL performans semasinda degil; bu havalimani icin dis dogrulama
kaynagimiz yok ve veri kalitesinin farkli olabilecegi akilda tutulmali.

Siralama aylarindan **Temmuz 2026 henuz yayimlanmamis** (seri Haziran 2026'da bitiyor),
dolayisiyla bu gosterge ozellik olarak kullanilamaz — yalnizca dogrulama icindir.
"""
    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text(body, encoding="utf-8")
    print(f"genel korelasyon r = {genel_ref:.3f}")
    print(per)
    print(f"\nrapor: {OUT_MD}")


if __name__ == "__main__":
    main()
