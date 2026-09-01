# The JOAS paper: rules and plan

Sources: <https://journals.open.tudelft.nl/joas/about/submissions> and
<https://github.com/open-aviation/joas-template> (both read on 2026-09-01).

The competition page **strongly** encourages teams, the top-placed ones in particular, to submit
a paper to JOAS. When picking the winner, the 2025 jury counted "a paper almost finished in the
JOAS format" as a clear advantage. So the paper is not an add-on left to the last week, it is
part of the delivery.

## Hard rules (breaking one gets the paper rejected outright)

| Rule | Note |
|---|---|
| **LaTeX is mandatory** | Word is not accepted |
| **A single `main.tex`** | `\input{}` / `\include{}` forbidden |
| **File names are fixed** | `main.tex`, `figures/`, `reference.bib` may not be renamed |
| **LaTeX must compile without errors** | the template writes this in red |
| Title ≤ 12 words, Title Case | no abbreviations |
| Abstract a single paragraph, ≤ 300 words | four elements required: purpose, design, findings, interpretation |
| Abbreviations only if used >10 times | otherwise write them out |
| Tables must be **plain `tabular`** | custom styling breaks the HTML version |
| Figures in `figures/`, `.png` / `.pdf` | lower case, no spaces in the name |
| `Figure \ref{}` in the text | do not write `Fig.` |
| **Open data statement** | MANDATORY section |
| **Reproducibility statement** | MANDATORY section |
| Author contributions (CRediT) | only when there is more than one author |

The submission is two files: the compiled PDF plus a ZIP of the LaTeX source.
Review is **open**: reviewer and author identities are shared and the reviews are published.
There is no fee.

## Choice of article type

`manuscript=article` (Research Article, General) is the right choice. The alternatives:

- **Open Software Focus**: requires the author to be the main developer of the software and the
  focus to be the software itself. Our contribution is the method, not a library, so it does not
  fit.
- **Open Data Focus**: we are not the ones compiling the data set, so it does not fit.

## Writing order (once the numbers are in)

1. **Method**: the easiest, since the code is already written, and the section that holds the
   most rationale.
2. **Data**: fed directly from the probe report.
3. **Results**: the `run_ablation.py` output is already a markdown table, to be converted to
   LaTeX.
4. **Related Work**: from `docs/literature.md`; **the citations whose full text has not been
   read will be removed** (they are listed in the last section of that file).
5. **Discussion**: the negative results go here, openly. A team was praised in 2025 for doing
   exactly this.
6. **Introduction** and **Abstract**: last.

## Candidate figures

| File | Contents | Source |
|---|---|---|
| `taxiout_distribution.png` | Taxi-out distribution per airport | probe §6 |
| `reference_coverage.png` | Official ATXOT level vs fallback share | `reference.official_coverage` |
| `ablation.png` | Feature family contributions | `run_ablation.py` |
| `retro_vs_causal.png` | The per-airport difference between the two anchors | a comparison of the two runs |
| `deicing_january.png` | January de-icing exposure (LSZH 18% to LTAI 0%) | METAR analysis |

The code that produces the figures has to be in the repository; the reproducibility statement
requires it.

## Compiling

```bash
cd docs/paper && make        # the template's own Makefile (latexmk)
```

`make` is not installed on this machine; if a TeX installation is needed, uploading to Overleaf
is the fastest route (the template is published on Overleaf too).
