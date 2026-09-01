# ADR-0003: The repository is English only

Date: 2026-09-01 · Status: accepted

## Context

The prize rules require the source code to be published on GitHub under GPLv3, with
documentation sufficient for a reader to understand and reproduce the results. The
repository is then forked by the challenge organisation and read by an international
jury. The 2025 jury criticised teams for sparse comments and for choices left
unjustified, so the documentation is judged, not just the score.

The work was originally written in Turkish because that is the language of the
conversation it grew out of. That would have failed the requirement for any reader
outside Turkey.

## Decision

Everything in the repository is written in English: identifiers, column names,
docstrings, comments, printed messages, commit messages and documentation. Turkish is
used only in conversation, never in the artefact.

## Consequences

- Column names changed across the whole pipeline, for example `referans_sn` became
  `reference_sec` and `pist_kalkis_onceki_15dk` became `rwy_dep_prev_15m`.
- **Derived data on disk had to be regenerated.** The external parquet files were
  written with the old column names, so the pipeline failed immediately after the
  rename with `ColumnNotFoundError: "latitude" not found`. The airport and EUROCONTROL
  adapters were re-run from their cached source files and the METAR columns were
  renamed in place rather than re-downloaded. Any similar rename in future has to
  account for data already written to disk, not only for code.
- Tests that matched on message text needed updating alongside the messages. Tests that
  assert on behaviour did not, which is an argument for preferring the latter.
