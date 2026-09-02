"""The freezing coefficient, against the published algorithm and against operations.

Two kinds of test here, and the distinction matters. Most assert the EUROCONTROL ATMAP
algorithm as published, so a transcription error shows up. Three assert the deliberate
departures from it, so that a later reader can tell a decision from a bug.
"""

from __future__ import annotations

import polars as pl

from taxiout.features import icing


def _rows(codes: list[str | None], temps: list[float], dews: list[float]) -> pl.DataFrame:
    return icing.attach(pl.DataFrame({
        "wxcodes": codes,
        "temperature_c": temps,
        "dewpoint_c": dews,
    }))


# --------------------------------------------------------------- the published algorithm


def test_snow_below_three_degrees_is_severe() -> None:
    out = _rows(["SN"], [-2.0], [-4.0])
    assert out["atmap_moisture"][0] == 5
    assert out["atmap_freezing"][0] == icing.SEVERE


def test_light_snow_is_moderate_not_severe() -> None:
    """`-SN` scores 4 and `SN` scores 5; the intensity marker changes the branch."""
    out = _rows(["-SN"], [0.0], [-1.0])
    assert out["atmap_moisture"][0] == 4
    assert out["atmap_freezing"][0] == icing.MODERATE


def test_freezing_rain_is_severe() -> None:
    out = _rows(["FZRA"], [0.0], [-1.0])
    assert out["atmap_freezing"][0] == icing.SEVERE


def test_rain_below_three_degrees_is_light() -> None:
    out = _rows(["RA"], [2.0], [-5.0])
    assert out["atmap_moisture"][0] == 3
    assert out["atmap_freezing"][0] == icing.LIGHT


def test_the_same_weather_above_three_degrees_scores_nothing() -> None:
    """The negative control for every case above: temperature is what gates it."""
    for code in ("SN", "FZRA", "-SN", "RA", "BR"):
        out = _rows([code], [10.0], [5.0])
        assert out["atmap_freezing"][0] == icing.NONE, code


def test_extreme_cold_with_any_moisture_is_severe() -> None:
    """Below minus fifteen, anything reported at all is severe."""
    out = _rows(["RA"], [-20.0], [-25.0])
    assert out["atmap_freezing"][0] == icing.SEVERE


def test_a_clear_cold_night_with_a_tight_dewpoint_is_light() -> None:
    """The frost branch. No precipitation, but the wing is cold-soaked and frosts over.

    This is the branch that gets left out of homemade de-icing proxies, because nothing
    in the present weather says anything is happening.
    """
    out = _rows([None], [-1.0], [-2.0])
    assert out["atmap_freezing"][0] == icing.LIGHT
    assert out["frost_risk"][0] is True


def test_a_clear_cold_night_with_dry_air_is_not_frost() -> None:
    out = _rows([None], [-1.0], [-15.0])
    assert out["atmap_freezing"][0] == icing.NONE
    assert out["frost_risk"][0] is False


def test_nothing_reported_and_mild_scores_zero() -> None:
    out = _rows([None], [15.0], [8.0])
    assert out["atmap_moisture"][0] is None
    assert out["atmap_freezing"][0] == icing.NONE


def test_a_missing_temperature_gives_no_answer_rather_than_zero() -> None:
    """Absent is not the same as benign, and a model told otherwise learns the wrong thing."""
    out = _rows(["SN"], [None], [None])
    assert out["atmap_freezing"][0] is None


# ------------------------------------------------------- the deliberate departures from it


def test_freezing_fog_is_severe_although_the_published_table_makes_it_light() -> None:
    """`FZFG` falls through to `FG` in the published table and scores 3.

    Freezing fog has among the shortest holdover times there are, and it appears 790
    times in our observations. Any FZ prefix is severe here. This is a decision, not a
    transcription error.
    """
    out = _rows(["FZFG"], [-1.0], [-1.5])
    assert out["atmap_moisture"][0] == 5
    assert out["atmap_freezing"][0] == icing.SEVERE


def test_freezing_drizzle_is_severe_for_the_same_reason() -> None:
    out = _rows(["FZDZ"], [0.0], [-0.5])
    assert out["atmap_freezing"][0] == icing.SEVERE


def test_mist_is_scored_below_light_snow() -> None:
    """ATMAP puts `BR` at 4, level with light snow. Mist at three degrees is an ordinary
    European winter morning, and at 4 it would fire the moderate branch across a large
    part of January. It sits at 3 here."""
    mist = _rows(["BR"], [1.0], [0.5])
    light_snow = _rows(["-SN"], [1.0], [0.5])
    assert mist["atmap_moisture"][0] == 3
    assert light_snow["atmap_moisture"][0] == 4
    assert mist["atmap_freezing"][0] < light_snow["atmap_freezing"][0]


# ----------------------------------------------------------------------------- plumbing


def test_a_frame_without_weather_columns_passes_through_unchanged() -> None:
    df = pl.DataFrame({"a": [1, 2]})
    assert icing.attach(df).columns == ["a"]


def test_the_first_matching_rule_wins() -> None:
    """`RASN` must not be read as `RA`; order in the rule list is the algorithm."""
    out = _rows(["RASN"], [0.0], [-1.0])
    assert out["atmap_moisture"][0] == 4
