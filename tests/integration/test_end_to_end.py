"""Uctan uca: sentetik veriden gecerli bir gonderim dosyasina.

Bu test tek tek modullerin dogrulugunu degil, **zincirin kopmadigini** kontrol eder.
Birim testleri her parcayi ayri dogruluyor; buradaki risk baska: bir kolon adi degisir,
bir birlestirme sessizce satir dusurur ve gonderim reddedilir. Yarismada bunun bedeli
bir gonderim turudur.

Fixture kucuk tutuldu; amac hiz degil, borularin gercekten uctan uca aktigi.
"""

from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import numpy as np
import polars as pl
import pytest

from taxiout.application import pipeline, submission
from taxiout.domain import reference

REPO = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def raw_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Kucuk bir sentetik veri seti uretir (12 ay egitim + siralama + sablon)."""
    out = tmp_path_factory.mktemp("veri") / "00_raw"
    subprocess.run(  # noqa: S603
        [sys.executable, str(REPO / "tests" / "make_fixture.py"),
         "--out", str(out), "--per-day", "40"],
        check=True, cwd=REPO,
    )
    return out


def test_fixture_reproduces_the_ranking_set_shape(raw_dir: Path) -> None:
    """Fixture gercek kurguyu taklit etmeli, yoksa test yanlis seyi dogrular."""
    rank = pl.read_parquet(raw_dir / "ranking.parquet")
    dep = rank.filter(pl.col("PHASE_mvt") == "DEP")
    arr = rank.filter(pl.col("PHASE_mvt") == "ARR")
    assert dep["BLOCK_TIME_UTC_mvt"].null_count() == dep.height, "DEP blok saati bos olmali"
    assert dep["TAXITIME_SEC_mvt"].null_count() == dep.height, "DEP taxi suresi bos olmali"
    assert arr["TAXITIME_SEC_mvt"].null_count() == 0, "ARR taxi suresi dolu olmali"
    assert dep["MVT_TIME_UTC_mvt"].null_count() == 0, "DEP kalkis saati dolu olmali"


def test_features_are_producible_on_the_ranking_set(raw_dir: Path) -> None:
    """Egitimde uretilen her oznitelik siralama setinde de uretilebilmeli.

    Uretilemeyen bir oznitelik, modelin egitimde ogrenip tahminde kaybettigi bilgidir;
    sessizce olursa RMSE'yi bozar ve nedeni gorunmez.

    Dis veriler iki tarafa da **ayni sekilde** verilmeli. Testin ilk hali bunu
    yapmiyordu ve gercek bir hatayi kacirdi: `make_submission.py` siralama tarafina
    gunluk ATFM tablosunu gecirmiyordu, 11 oznitelik sessizce dusuyordu.
    """
    inputs = pipeline.load_inputs(raw_dir)
    fit = pipeline.build_features(inputs)
    rank_inputs = replace(inputs, movements=pipeline.prepare_movements(
        pl.read_parquet(raw_dir / "ranking.parquet")))
    rank = pipeline.build_features(rank_inputs)

    eksik = set(pipeline.feature_columns(fit)) - set(rank.columns)
    assert eksik == set(), f"siralama setinde uretilemeyen oznitelikler: {sorted(eksik)}"


def test_holdout_mirrors_the_ranking_set_shape(raw_dir: Path) -> None:
    """Dogrulama parcasi siralama setinin seklini tasimali.

    Siralama seti simetrik degil: Ocak'ta 10 havalimani, Temmuz'da yalnizca uc tanesi
    (docs/facts.md R03). Dogrulama bunu taklit etmezse Temmuz'u oldugundan onemli
    sanip yanlis modeli seceriz. Temmuz'un diger havalimanlari bilerek egitimde kalir.
    """
    inputs = pipeline.load_inputs(raw_dir)
    split = pipeline.seasonal_split(pipeline.build_features(inputs), inputs.movements)

    ay = pl.col("MVT_TIME_UTC_mvt").dt.month()
    assert set(split.val.select(ay.unique()).to_series().to_list()) == {1, 7}

    temmuz_apt = set(
        split.val.filter(ay == 7)[pipeline.APT].unique().to_list()
    )
    ocak_apt = set(split.val.filter(ay == 1)[pipeline.APT].unique().to_list())
    assert temmuz_apt <= set(pipeline.JULY_AIRPORTS), f"Temmuz'da fazladan havalimani: {temmuz_apt}"
    assert len(ocak_apt) > len(temmuz_apt), "Ocak daha genis olmali"

    # satirlar kesismemeli
    ortak = set(split.fit["MVT_ID_mvt"].to_list()) & set(split.val["MVT_ID_mvt"].to_list())
    assert ortak == set(), "ayni hareket hem egitimde hem dogrulamada olamaz"

    # Temmuz'un dogrulamada olmayan havalimanlari egitimde kalmali
    egitim_temmuz = set(split.fit.filter(ay == 7)[pipeline.APT].unique().to_list())
    assert egitim_temmuz, "Temmuz'un diger havalimanlari egitimde olmali"
    assert not (egitim_temmuz & temmuz_apt)


def test_reference_is_fitted_without_the_validation_months(raw_dir: Path) -> None:
    """Sizinti kontrolu: referans dogrulama aylarini gormemeli.

    Gorseydi OOF sayilari yalanci sekilde iyilesir ve board'da geri alinamazdi.
    """
    inputs = pipeline.load_inputs(raw_dir)
    ay = pl.col("MVT_TIME_UTC_mvt").dt.month()
    sadece_ocak_temmuz = inputs.movements.filter(ay.is_in(pipeline.HOLDOUT_MONTHS))
    kalan = inputs.movements.filter(~ay.is_in(pipeline.HOLDOUT_MONTHS))

    t_kalan = reference.fit_reference(kalan)["apt"]
    t_hepsi = reference.fit_reference(inputs.movements)["apt"]
    assert sadece_ocak_temmuz.height > 0
    # aylar cikarilinca ornek sayisi dusmeli: tablo gercekten farkli veriden uretiliyor
    assert t_kalan["n_apt"].sum() < t_hepsi["n_apt"].sum()


def test_full_run_produces_a_valid_submission(raw_dir: Path, tmp_path: Path) -> None:
    inputs = pipeline.load_inputs(raw_dir)
    tables = reference.fit_reference(inputs.movements)
    fit = reference.apply_reference(
        pipeline.build_features(inputs).filter(pl.col(pipeline.TARGET).is_not_null()), tables
    )
    rank_inputs = replace(inputs, movements=pipeline.prepare_movements(
        pl.read_parquet(raw_dir / "ranking.parquet")))
    rank = reference.apply_reference(pipeline.build_features(rank_inputs), tables)

    cols = [c for c in pipeline.feature_columns(fit) if c in rank.columns]
    split = pipeline.Split(fit=fit, val=rank, columns=cols)
    pred = pipeline.train_predict(split, cols, rounds=30)

    assert np.isfinite(pred).all(), "tahminlerde NaN/sonsuz olmamali"
    assert (pred >= 0).all(), "negatif taxi suresi fiziksel olarak imkansiz"

    template = pl.read_parquet(raw_dir / "submitting.parquet")
    pred_df = rank.select("MVT_ID_mvt").with_columns(
        pl.Series(pipeline.TARGET, pred.astype(np.float64))
    ).join(template.select("MVT_ID_mvt"), on="MVT_ID_mvt", how="semi")

    out = tmp_path / "keen-hamburger_v1.parquet"
    submission.write(pred_df, template, out)

    written = pl.read_parquet(out)
    assert written.columns == ["MVT_ID_mvt", pipeline.TARGET]
    assert written["MVT_ID_mvt"].to_list() == template["MVT_ID_mvt"].to_list()
    assert written[pipeline.TARGET].null_count() == 0


def test_causal_run_also_completes(raw_dir: Path) -> None:
    """Nedensel varyant makale icin gerekli; kirilirsa sessizce kaybolmasin."""
    inputs = pipeline.load_inputs(raw_dir)
    feats = pipeline.build_features(inputs, causal=True)
    split = pipeline.seasonal_split(feats, inputs.movements)
    pred = pipeline.train_predict(split, split.columns, rounds=30)
    scores = pipeline.evaluate(split, pred)
    assert scores["toplam"] > 0
    assert not [c for c in split.columns if "sonraki" in c]


def test_submission_script_drops_no_features(raw_dir: Path, tmp_path: Path) -> None:
    """Uretim betigini gercekten calistirir ve hicbir ozniteligin dusmedigini dogrular.

    Bu testin var olma nedeni somut: `make_submission.py` `Inputs`'u konumsal
    argumanlarla kuruyordu; `Inputs`'a gunluk ATFM alani eklendiginde siralama tarafi
    sessizce onsuz kaldi ve 11 oznitelik dustu. Boru hatti fonksiyonlarini test etmek
    bunu yakalamiyor cunku hata betigin kendi kurulumundaydi — bu yuzden betik
    bir alt surec olarak calistiriliyor.
    """
    data_dir = tmp_path / "veri"
    (data_dir / "00_raw").mkdir(parents=True)
    for f in raw_dir.iterdir():
        (data_dir / "00_raw" / f.name).write_bytes(f.read_bytes())

    result = subprocess.run(  # noqa: S603
        [sys.executable, str(REPO / "scripts" / "make_submission.py"),
         "--data-dir", str(data_dir), "--team", "keen-hamburger",
         "--rounds", "20", "--seeds", "1"],
        check=True, cwd=REPO, capture_output=True, text=True,
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )
    assert "UYARI: siralama setinde uretilemeyen" not in result.stdout, (
        "gonderim yolunda oznitelik dusuyor:\n" + result.stdout
    )
    written = list((data_dir / "04_submissions").glob("keen-hamburger_v*.parquet"))
    assert len(written) == 1, f"tam bir gonderim dosyasi beklendi, bulunan: {written}"
    template = pl.read_parquet(raw_dir / "submitting.parquet")
    assert pl.read_parquet(written[0]).height == template.height
