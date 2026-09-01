"""Oznitelik aileleri — ablation'in birimi.

Neden ayri bir kayit defteri: 2025 birincisinin makalesinde katkinin sunumu **tek bir
oznitelik-ailesi x RMSE tablosuydu** (P06) ve o tabloyu dogrudan siralama seti uzerinde
urettiler (P04). Yani gonderimlerimiz ayar denemesi degil, tasarlanmis bir deney olmali;
bunun icin "su aileyi cikar" tek bir isimle ifade edilebilmeli.

Aile adlari, `docs/literature.md` §4'te alinti verilen Wang ve ark. (Sangay Pudong, 2018)
taksonomisiyle hizali: SIFI (anlik akis), SCFI (kumulatif akis), AQLI (kuyruk uzunlugu),
SRDI (slot/kaynak talebi).

`test_groups.py` her oznitelik kolonunun **tam olarak bir** aileye dustugunu dogrular.
Yeni bir oznitelik eklenip buraya yazilmazsa test kirilir; boylece hicbir oznitelik
ablation'in disinda sessizce birikemez.
"""

from __future__ import annotations

import re

# Sira onemli: bir kolon ilk eslesen aileye atanir.
GROUPS: dict[str, list[str]] = {
    # --- yerlesim ve engelsiz taban (AQLI oncesi statik bilgi)
    "geometri": [
        r"^ADEP_mvt$", r"^RUNWAY_mvt$", r"^STAND_mvt$",
        r"^pist_sayisi$", r"^en_uzun_pist_ft$", r"^ort_pist_ft$",
        r"^referans_",
    ],
    # --- pist kuyrugu (AQLI): Idris'in en guclu degiskeninin dairesel olmayan vekilleri
    "pist_kuyrugu": [
        r"^pist_kalkis_", r"^onceki_kalkis_sn$", r"^sonraki_kalkis_sn$",
        r"^pist_servis_araligi_sn$",
    ],
    # --- havalimani genelinde akis (SIFI + SCFI)
    "havalimani_akisi": [r"^apt_kalkis_", r"^apt_inis_", r"^inis_kalkis_orani_"],
    # --- yuzeyin canli tikanikligi; siralama setinde de hesaplanabilir (D09)
    "taxi_in_baskisi": [r"^varis_taxi_"],
    # --- pist konfigurasyonu cikarimi
    "pist_konfigurasyonu": [r"^kalkis_pistleri$", r"^inis_pistleri$", r"^aktif_pist_sayisi$"],
    # --- departure-fix vekili (Lee ve ark. 2016)
    "yonlendirme": [
        r"^kalkis_kerterizi$", r"^kalkis_sektoru$", r"^sektor_kalkis_", r"^ucus_mesafesi_km$",
    ],
    # --- asagi-akis kisitlari / slot talebi (SRDI; Idris'in dorduncu faktoru)
    "atfm": [
        r"^atfm_suruklenme_sn$", r"^lobt_cipa_farki_sn$", r"^plan_sapmasi_sn$",
        r"^eobt_sapmasi_sn$", r"^yonlendirildi$",
    ],
    "stand_donusu": [r"^stand_donus_sn$"],
    # --- hava; Ocak'ta de-icing rejimini tasiyan aile (W03)
    "hava": [
        r"^sicaklik_c$", r"^cig_noktasi_c$", r"^cig_farki_c$", r"^gorus_km$", r"^ruzgar_ms$",
        r"^ruzgar_yon$", r"^yagis_mm$", r"^tavan_m$", r"^donma_yagisi$", r"^kar$", r"^sis$",
        r"^gok_gurultusu$", r"^deicing_vekili$", r"^dusuk_gorus$", r"^gozlem_yasi_dk$",
    ],
    "takvim": [r"^saat$", r"^hafta_gunu$", r"^ay$", r"^gun_dakikasi$"],
    "ucak": [
        r"^AIRCRAFT_TYPE_", r"^WK_TBL_CAT_flt$", r"^MARKET_SEGMENT_flt$",
        r"^AIRCRAFT_OPERATOR_flt$",
    ],
    # --- EUROCONTROL gunluk havalimani durumu; ayri aile cunku nedensel modda
    # kullanilamiyor (gun boyunun toplami) ve dis kaynakli
    "atfm_gunluk": [
        r"^atfm_duzenlenen_oran$", r"^atfm_slot_", r"^gunluk_kalkis$", r"^gunluk_inis$",
        r"^varis_atfm_gecikme_dk$", r"^varis_gecikme_",
    ],
    # --- NM M3 blok saatinden turetilenler; ayri aile cunku tum mimariyi belirliyor (Q02)
    "nm_aobt": [r"^naif_taxi_sn$", r"^nm_eslesti$"],
}

_COMPILED = {name: [re.compile(p) for p in pats] for name, pats in GROUPS.items()}


def group_of(column: str) -> str | None:
    """Kolonun ait oldugu aile, ya da hicbirine uymuyorsa None."""
    for name, patterns in _COMPILED.items():
        if any(p.match(column) for p in patterns):
            return name
    return None


def assign(columns: list[str]) -> dict[str, list[str]]:
    """Aile -> o ailedeki kolonlar. Eslesmeyenler 'ATANMAMIS' altinda toplanir."""
    out: dict[str, list[str]] = {name: [] for name in GROUPS}
    out["ATANMAMIS"] = []
    for c in columns:
        out[group_of(c) or "ATANMAMIS"].append(c)
    return out


def select(columns: list[str], drop: set[str] | None = None) -> list[str]:
    """Verilen aileler cikarilmis kolon listesi.

    Ailesi olmayan kolonlar **tutulur** — ablation eksik bir kayit yuzunden sessizce
    oznitelik dusurmemeli. Eksik kayit `test_groups.py` ile yakalanir.
    """
    drop = drop or set()
    bilinmeyen = drop - set(GROUPS)
    if bilinmeyen:
        raise KeyError(f"tanimsiz oznitelik ailesi: {sorted(bilinmeyen)}")
    return [c for c in columns if group_of(c) not in drop]
