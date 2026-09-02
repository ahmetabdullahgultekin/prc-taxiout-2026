"""EUROCONTROL's own freezing-conditions coefficient, from the METAR present weather.

January is 71 percent of the ranking set, and the dominant January effect on taxi-out is
de-icing. The de-icing flag this project started with is a homemade boolean: a freezing
or snow code, or any precipitation at or below three degrees. EUROCONTROL publishes a
graded coefficient instead, in the ATMAP methodology (PRU Technical Note, 2011), and it
is worth preferring for a reason beyond quality: it is the same organisation that runs
this competition and computes the indicator being predicted.

The algorithm, verbatim in structure:

    visible moisture, first match wins on the present-weather string
        FZRA 5 | +RA 4 | SG 4 | RASN 4 | -SN 4 | SN 5 | BR 4
        RA 3 | PL 3 | IC 3 | GR 3 | GS 3 | UP 3 | FG 3 | DZ 3
        anything else 0; nothing reported at all, null

    freezing coefficient
        T <= 3 and moisture == 5                    -> 4   severe
        T < -15 and moisture is not null            -> 4
        T <= 3 and moisture == 4                    -> 3   moderate
        T <= 3 and (moisture == 3 or T - Td < 3)    -> 1   light, or frost risk
        otherwise                                   -> 0

Two departures from it, both deliberate, because ATMAP was written to score *airport
weather difficulty* and this is being used to predict *de-icing service time*:

**Freezing drizzle and freezing fog are promoted to severe.** The published table tests
`FZRA` as a literal, so `FZDZ` falls through to `DZ` and `FZFG` to `FG`, both scoring 3,
"light". Operationally they are the opposite: freezing drizzle and freezing fog have the
shortest holdover times of any condition. `FZFG` appears 790 times in our observations.
Any `FZ` prefix scores 5 here.

**Mist is separated from light snow.** ATMAP scores `BR` at 4, level with `+RA` and
`-SN`. Mist at three degrees is an ordinary European winter morning and would fire the
moderate branch on a large share of January. It is kept, at 3, and exposed as its own
column so the model can price it rather than inheriting ATMAP's weighting.

The frost branch, `T - Td < 3` with no precipitation at all, is the one people leave out.
It is a clear cold night with a cold-soaked wing, which still needs a spray.
"""

from __future__ import annotations

import polars as pl

# Ordered: the first pattern that matches the present-weather string wins, exactly as in
# the published algorithm. `FZ` is lifted to the front, see the module docstring.
MOISTURE_RULES: list[tuple[str, int]] = [
    ("FZ", 5),      # any freezing precipitation, including FZDZ and FZFG
    ("+RA", 4),
    ("SG", 4),      # snow grains
    ("RASN", 4),
    ("-SN", 4),
    ("SN", 5),
    ("BR", 3),      # mist, deliberately below ATMAP's 4
    ("RA", 3),
    ("PL", 3),      # ice pellets
    ("IC", 3),      # ice crystals
    ("GR", 3),      # hail
    ("GS", 3),      # small hail
    ("UP", 3),      # unidentified precipitation
    ("FG", 3),
    ("DZ", 3),
]

SEVERE, MODERATE, LIGHT, NONE = 4, 3, 1, 0


def visible_moisture(codes: pl.Expr) -> pl.Expr:
    """The ATMAP visible-moisture score, or null when nothing was reported."""
    expr = pl.when(codes.is_null()).then(None)
    for pattern, score in MOISTURE_RULES:
        expr = expr.when(codes.str.contains(pattern, literal=True)).then(score)
    return expr.otherwise(0).cast(pl.Int8)


def freezing_coefficient(
    temperature_c: pl.Expr, dewpoint_c: pl.Expr, moisture: pl.Expr
) -> pl.Expr:
    """Severity of freezing conditions: 0 none, 1 light, 3 moderate, 4 severe."""
    cold = temperature_c <= 3.0
    spread = temperature_c - dewpoint_c
    return (
        pl.when(temperature_c.is_null())
        .then(None)
        .when(cold & (moisture == 5))
        .then(SEVERE)
        .when((temperature_c < -15.0) & moisture.is_not_null())
        .then(SEVERE)
        .when(cold & (moisture == 4))
        .then(MODERATE)
        .when(cold & ((moisture == 3) | (spread < 3.0)))
        .then(LIGHT)
        .otherwise(NONE)
        .cast(pl.Int8)
    )


def attach(df: pl.DataFrame, codes: str = "wxcodes") -> pl.DataFrame:
    """Add the coefficient and its parts to a frame that already carries METAR columns.

    Three columns rather than one. The coefficient is the operational summary; the
    moisture score is what ATMAP grades the airport on and is not the same question; and
    the frost flag isolates the branch with no precipitation in it, which is a different
    physical process and a different de-icing procedure from active snow.
    """
    if codes not in df.columns or "temperature_c" not in df.columns:
        return df
    # Cast rather than assume: a stretch of observations with no present weather at all
    # arrives as a Null-typed column, and the string matching below raises on it. That
    # is a fine month at a quiet airport, not an error.
    moisture = visible_moisture(pl.col(codes).cast(pl.String))
    return df.with_columns(
        atmap_moisture=moisture,
        atmap_freezing=freezing_coefficient(
            pl.col("temperature_c"), pl.col("dewpoint_c"), moisture
        ),
        # A clear cold night: no precipitation reported, but the wing is below the
        # dewpoint and frosts over. Short spray, and invisible to a precipitation flag.
        frost_risk=(
            (pl.col("temperature_c") <= 3.0)
            & ((pl.col("temperature_c") - pl.col("dewpoint_c")) < 3.0)
            & (pl.col(codes).cast(pl.String).is_null() | (moisture == 0))
        ),
    )
