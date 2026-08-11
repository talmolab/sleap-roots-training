"""Structural contract tests for the labeling-package documentation (tasks 8.6/8.7).

CI-safe: reads the two docs from disk. The point of porting the vault command doc was that
it stops being a description of scripts on one machine and becomes instructions for
commands this repo ships — so the test that matters is that every command and every option
the docs tell someone to run **exists**. A workflow doc that has drifted from the CLI is
worse than none: it fails in front of the person following it, after they have staged a
download.

Also pins the two obligations the port carries: design.md F9's dropped manual `pd.concat`
step, and Decision 6's re-derive path with the reason stated rather than only the
instruction (the spec's Continued Labeling scenario).
"""

from __future__ import annotations

import re
import shlex
from pathlib import Path

import pytest

from sleap_roots_training import cli

ROOT = Path(__file__).resolve().parents[1]
GUIDE = ROOT / "docs" / "labeling-packages.md"
COMMAND_DOC = ROOT / ".claude" / "commands" / "build-labeling-package.md"

_FENCE = re.compile(r"```([^\n]*)\n(.*?)```", re.DOTALL)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8").replace("\r\n", "\n")


def shell_blocks(text: str) -> list[str]:
    """Return the bodies of shell-tagged fences, with line continuations joined."""
    return [
        body.replace("\\\n", " ")
        for tag, body in _FENCE.findall(text)
        if tag.strip().lower() in {"bash", "sh", "shell", "console"}
    ]


def documented_invocations(text: str) -> list[list[str]]:
    """Return every ``sleap-roots-training labeling ...`` command line, tokenized."""
    invocations = []
    for block in shell_blocks(text):
        for line in block.splitlines():
            line = line.strip()
            if "sleap-roots-training labeling" not in line:
                continue
            tokens = shlex.split(line, comments=True)
            start = tokens.index("labeling")
            invocations.append(tokens[start + 1 :])
    return invocations


@pytest.fixture(scope="module")
def labeling_group():
    return cli.main.commands["labeling"]


def test_both_docs_exist():
    assert GUIDE.is_file(), f"missing contributor guide: {GUIDE}"
    assert COMMAND_DOC.is_file(), f"missing command doc: {COMMAND_DOC}"


@pytest.mark.parametrize("doc", [GUIDE, COMMAND_DOC], ids=["guide", "command"])
def test_every_documented_command_exists(doc, labeling_group):
    invocations = documented_invocations(read(doc))

    assert invocations, f"{doc.name} documents no `labeling` command"
    for tokens in invocations:
        assert (
            tokens[0] in labeling_group.commands
        ), f"{doc.name} runs `labeling {tokens[0]}`, which is not a command"


def _known_options(command) -> set[str]:
    """Return every long option a command accepts."""
    return {
        opt for param in command.params for opt in param.opts if opt.startswith("--")
    }


@pytest.mark.parametrize("doc", [GUIDE, COMMAND_DOC], ids=["guide", "command"])
def test_every_documented_option_exists(doc, labeling_group):
    """The drift that actually bites: an option renamed in `cli.py` and not here."""
    for tokens in documented_invocations(read(doc)):
        # A renamed *subcommand* would make this a KeyError rather than a clean assertion,
        # which is a rougher failure than the option case (blocking review of #40). The
        # command-existence test above catches it first, but only when both run.
        assert tokens[0] in labeling_group.commands, (
            f"{doc.name} runs `labeling {tokens[0]}`, which is not a command "
            f"(commands: {sorted(labeling_group.commands)})"
        )
        command = labeling_group.commands[tokens[0]]
        known = {opt for param in command.params for opt in param.opts}
        for token in tokens[1:]:
            if token.startswith("--"):
                assert token in known, (
                    f"{doc.name} passes {token} to `labeling {tokens[0]}`, which does not "
                    f"accept it (accepts: {sorted(known)})"
                )


def test_every_required_option_is_documented_at_least_once(labeling_group):
    """A doc that omits a required option produces a usage error, not a package."""
    text = read(GUIDE) + read(COMMAND_DOC)
    documented = {
        token
        for tokens in documented_invocations(text)
        for token in tokens
        if token.startswith("--")
    }
    for name, command in labeling_group.commands.items():
        for param in command.params:
            if getattr(param, "required", False) and param.opts[0].startswith("--"):
                assert (
                    param.opts[0] in documented
                ), f"`labeling {name}` requires {param.opts[0]}, which neither doc shows"


def test_every_option_is_documented_at_least_once(labeling_group):
    """Optional options too, not only required ones (blocking review of #40).

    The fence only covered ``required=True``, so a new *optional* option could go
    undocumented forever — and the interesting options here are optional by design:
    ``--views-per-plant``, ``--seed``, and ``--total-views`` all change what ends up in the
    package, and ``--accession-names`` changes every filename in it. There is no gap today;
    this is what keeps it that way.
    """
    text = read(GUIDE) + read(COMMAND_DOC)
    documented = {
        token
        for tokens in documented_invocations(text)
        for token in tokens
        if token.startswith("--")
    }
    undocumented = sorted(
        f"labeling {name} {option}"
        for name, command in labeling_group.commands.items()
        for option in _known_options(command)
        if option not in documented and option != "--help"
    )
    assert (
        not undocumented
    ), "these CLI options appear in neither doc:\n  " + "\n  ".join(undocumented)


def test_the_guide_documents_the_package_layout():
    """Decision 3 makes the layout a contract; a contributor has to be able to read it."""
    guide = read(GUIDE)

    for piece in (
        "package_metadata.yaml",
        "sample_manifest.csv",
        "images/",
        "README.md",
        "_labels.v000.slp",
    ):
        assert piece in guide, f"guide does not show {piece} in the package layout"


def test_the_accession_lookup_is_documented_as_a_manual_prerequisite():
    """design.md F2: nothing in this repo talks to Bloom, so it has to be handed the names."""
    command_doc = read(COMMAND_DOC)

    assert "accessions" in command_doc
    assert "manual prerequisite" in command_doc.lower()


def test_the_manual_qc_concat_step_is_gone():
    """Obligation from design.md F9.

    The vault doc told the reader to `pd.concat` the per-age-group QC files, because the
    script's glob branch could not resolve a wildcard in a *directory* component. The port
    fixed that, so keeping the step would preserve a workaround for a bug that no longer
    exists — and the CLI now takes the glob directly.

    Scoped to code fences on purpose. What must be gone is the *instruction*; the doc says
    in prose that the step was dropped and why, which is worth keeping and is not a step.
    A guard that forbade the mention would fire on the sentence explaining the fix.
    """
    command_doc = read(COMMAND_DOC)
    fenced = "\n".join(body for _tag, body in _FENCE.findall(command_doc))

    assert "pd.concat" not in fenced
    assert "10_final_data.csv" in command_doc
    assert "Do not concatenate" in command_doc


@pytest.mark.parametrize("doc", [GUIDE, COMMAND_DOC], ids=["guide", "command"])
def test_continued_labeling_is_documented_as_re_derive_and_republish(doc):
    """The spec's Continued Labeling scenario, in both docs a reader might reach for."""
    text = read(doc)

    assert "re-derive" in text.lower() or "re-select" in text.lower()
    assert "bloomctl download" in text
    assert "--version v001" in text


def test_the_guide_states_why_editing_a_published_package_is_not_supported():
    """ "...and explains why" — the reason is the part that stops someone trying it anyway."""
    guide = read(GUIDE)

    assert "save_slp" in guide
    assert "if it is still available" in guide
    assert "repaired_from" in guide


def test_the_docs_have_no_placeholders():
    for doc in (GUIDE, COMMAND_DOC):
        text = read(doc)
        for placeholder in ("TODO", "TBD"):
            assert placeholder not in text, f"{doc.name} still has a {placeholder}"


def test_the_command_doc_points_at_the_contributor_guide():
    """The checklist stays a checklist only if the reasoning lives somewhere findable."""
    assert "docs/labeling-packages.md" in read(COMMAND_DOC)
