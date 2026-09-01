"""The local check runner must cover everything the CI workflow runs.

GitHub Actions cannot execute on this account, so `scripts/verify.py` is the only thing
actually verifying the repository. That makes drift between the two dangerous in a
specific way: a check added to the workflow looks like it is running, and is not
running anywhere at all.

The comparison is on the commands, not on the file text, so formatting changes to either
file are free and a new check is not.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))

import verify  # noqa: E402


def _ci_commands() -> list[str]:
    """Every command line inside a `run:` block of the workflow.

    Indentation decides where a block ends, which is how YAML itself decides. The first
    version of this matched on `run: ` and so read the `|` of a block scalar as if it
    were the command, collecting nothing from the multi-line steps. The negative control
    below is what caught it.
    """
    text = (REPO / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    out: list[str] = []
    block_indent: int | None = None

    for line in text.split("\n"):
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip())

        if block_indent is not None:
            if indent > block_indent:
                out.append(line.strip())
                continue
            block_indent = None

        match = re.match(r"^\s*-?\s*run:\s*(.*)$", line)
        if match:
            value = match.group(1).strip()
            if value in {"|", ">", "|-", ">-", ""}:
                block_indent = indent
            else:
                out.append(value)

    return [c for c in out if c and not c.startswith("#")]


def _tokens(commands: list[str]) -> set[str]:
    """The parts worth comparing: entry points and script paths, not their arguments."""
    keep: set[str] = set()
    for cmd in commands:
        for token in cmd.split():
            if token.endswith(".py") or token in {"ruff", "pytest"}:
                keep.add(token.replace("\\", "/").lstrip("./"))
    return keep


def test_every_ci_command_is_covered_locally() -> None:
    local = _tokens([" ".join(cmd) for _, cmd in verify.steps(Path("/tmp/x"))])
    # verify.py invokes the tools as modules, so record those names too.
    local |= {"ruff", "pytest"}

    ci = _tokens(_ci_commands())
    ci.discard("pip")  # installing dependencies is not a check

    missing = {c for c in ci if not any(c in item for item in local)}
    assert not missing, (
        f"the workflow runs {sorted(missing)} and scripts/verify.py does not. "
        "Actions cannot run on this account, so those checks run nowhere."
    )


def test_the_workflow_really_does_run_checks() -> None:
    """A negative control: if the parser returned nothing the test above is vacuous."""
    ci = _tokens(_ci_commands())
    assert "pytest" in ci
    assert any(c.startswith("scripts/") for c in ci)
