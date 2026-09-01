"""Oznitelik ailesi kaydinin butunlugu.

Buradaki asil test `test_every_produced_feature_has_a_group`. Amaci sadece bir
tutarlilik kontrolu degil: bir oznitelik aileye yazilmazsa ablation tablosunda
gorunmez, yani hicbir deneyle sinanmadan modelde kalir. Test kirilarak bunu
imkansiz kilar.
"""

from __future__ import annotations

import pytest

from taxiout.features import groups

# Boru hattinin urettigi kolonlar (fixture uzerinde uctan uca kosudan alindi) +
# referans modulunun sonradan ekledikleri.
PRODUCED = [
    "ADEP_mvt", "AIRCRAFT_OPERATOR_flt", "AIRCRAFT_TYPE_flt", "AIRCRAFT_TYPE_mvt",
    "MARKET_SEGMENT_flt", "RUNWAY_mvt", "STAND_mvt", "WK_TBL_CAT_flt", "aktif_pist_sayisi",
    "apt_inis_onceki_5dk", "apt_inis_onceki_10dk", "apt_inis_onceki_15dk",
    "apt_inis_onceki_30dk", "apt_inis_onceki_60dk",
    "apt_inis_sonraki_5dk", "apt_inis_sonraki_10dk", "apt_inis_sonraki_15dk",
    "apt_inis_sonraki_30dk", "apt_inis_sonraki_60dk",
    "apt_kalkis_onceki_5dk", "apt_kalkis_onceki_10dk", "apt_kalkis_onceki_15dk",
    "apt_kalkis_onceki_30dk", "apt_kalkis_onceki_60dk",
    "apt_kalkis_sonraki_5dk", "apt_kalkis_sonraki_10dk", "apt_kalkis_sonraki_15dk",
    "apt_kalkis_sonraki_30dk", "apt_kalkis_sonraki_60dk",
    "atfm_suruklenme_sn", "ay", "cig_farki_c", "cig_noktasi_c", "deicing_vekili",
    "donma_yagisi", "dusuk_gorus", "en_uzun_pist_ft", "eobt_sapmasi_sn", "gok_gurultusu",
    "gorus_km", "gozlem_yasi_dk", "gun_dakikasi", "hafta_gunu", "inis_kalkis_orani_30dk",
    "inis_pistleri", "kalkis_kerterizi", "kalkis_pistleri", "kalkis_sektoru", "kar",
    "lobt_cipa_farki_sn", "naif_taxi_sn", "nm_eslesti", "onceki_kalkis_sn", "ort_pist_ft",
    "pist_kalkis_onceki_5dk", "pist_kalkis_onceki_10dk", "pist_kalkis_onceki_15dk",
    "pist_kalkis_onceki_30dk", "pist_kalkis_onceki_60dk",
    "pist_kalkis_sonraki_5dk", "pist_kalkis_sonraki_10dk", "pist_kalkis_sonraki_15dk",
    "pist_kalkis_sonraki_30dk", "pist_kalkis_sonraki_60dk",
    "pist_sayisi", "pist_servis_araligi_sn", "plan_sapmasi_sn", "ruzgar_ms", "saat",
    "sektor_kalkis_onceki_15dk", "sektor_kalkis_onceki_30dk", "sicaklik_c", "sis",
    "sonraki_kalkis_sn", "stand_donus_sn", "tavan_m", "ucus_mesafesi_km",
    "varis_taxi_medyan", "varis_taxi_sayi", "yagis_mm", "yonlendirildi",
    # airport_state.attach ciktilari (EUROCONTROL gunluk)
    "atfm_duzenlenen_oran", "atfm_slot_gec_oran", "atfm_slot_erken_oran",
    "gunluk_kalkis", "gunluk_inis", "varis_atfm_gecikme_dk",
    "varis_gecikme_hava_dk", "varis_gecikme_atc_kapasite_dk",
    "varis_gecikme_meydan_kapasite_dk", "varis_gecikme_atc_personel_dk",
    "varis_gecikme_atc_ekipman_dk",
    # reference.apply_reference ciktilari
    "referans_sn", "referans_seviye", "referans_ornek",
]


def test_every_produced_feature_has_a_group() -> None:
    orphans = [c for c in PRODUCED if groups.group_of(c) is None]
    assert orphans == [], (
        f"su oznitelikler hicbir aileye ait degil, ablation'da gorunmezler: {orphans}"
    )


def test_no_feature_falls_into_two_groups() -> None:
    """Kolon birden fazla ailenin desenine uyarsa ablation sonucu yaniltici olur."""
    import re

    for c in PRODUCED:
        matches = [
            name for name, pats in groups.GROUPS.items()
            if any(re.compile(p).match(c) for p in pats)
        ]
        assert len(matches) == 1, f"{c} birden cok aileye uyuyor: {matches}"


def test_every_group_is_non_empty() -> None:
    """Bos bir aile, yeniden adlandirilmis ama guncellenmemis bir desendir."""
    assigned = groups.assign(PRODUCED)
    empty = [name for name in groups.GROUPS if not assigned[name]]
    assert empty == [], f"bos oznitelik ailesi: {empty}"


def test_select_drops_exactly_the_named_group() -> None:
    kept = groups.select(PRODUCED, drop={"hava"})
    assert "sicaklik_c" not in kept
    assert "deicing_vekili" not in kept
    assert "pist_kalkis_onceki_15dk" in kept
    assert len(kept) == len(PRODUCED) - len(groups.assign(PRODUCED)["hava"])


def test_select_rejects_unknown_group_instead_of_silently_ignoring() -> None:
    with pytest.raises(KeyError, match="tanimsiz"):
        groups.select(PRODUCED, drop={"hava_durumu"})


def test_unknown_columns_are_kept_not_dropped() -> None:
    """Kayitta olmayan bir kolon ablation tarafindan sessizce dusurulmemeli."""
    kept = groups.select([*PRODUCED, "yepyeni_oznitelik"], drop={"hava"})
    assert "yepyeni_oznitelik" in kept
