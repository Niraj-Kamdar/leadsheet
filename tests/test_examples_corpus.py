from pathlib import Path

import pytest

from leadsheet import compiler, dsl
from leadsheet.schema import PieceSchema
from leadsheet.theory_check import validate as theory_validate

EXAMPLES_DIR = Path(__file__).parent.parent / "examples"
EXAMPLE_PATHS = sorted(EXAMPLES_DIR.glob("*.leadsheet"))

# Chords whose theory-check "detected: null" mismatch is expected and benign
# (power chords -- root+fifth dyads musicpy's detector can't pattern-match
# to a chord family), same convention documented in genre-recipes.md.
EXPECTED_WARNING_FILES = {"doom-metal-dirge.leadsheet"}


def test_examples_directory_is_not_empty():
    assert EXAMPLE_PATHS, f"no .leadsheet files found under {EXAMPLES_DIR}"


@pytest.mark.parametrize("path", EXAMPLE_PATHS, ids=[p.name for p in EXAMPLE_PATHS])
def test_example_parses_and_matches_piece_schema(path):
    parsed = dsl.parse_dsl(path.read_text())
    PieceSchema(**parsed)


@pytest.mark.parametrize("path", EXAMPLE_PATHS, ids=[p.name for p in EXAMPLE_PATHS])
def test_example_passes_theory_check(path):
    parsed = dsl.parse_dsl(path.read_text())
    result = theory_validate(parsed)
    assert result.valid, result.errors
    if path.name not in EXPECTED_WARNING_FILES:
        assert result.warnings == []


@pytest.mark.parametrize("path", EXAMPLE_PATHS, ids=[p.name for p in EXAMPLE_PATHS])
def test_example_compiles_to_a_musicpy_piece(path):
    parsed = dsl.parse_dsl(path.read_text())
    schema = PieceSchema(**parsed)
    piece = compiler.compile_piece(schema)
    assert len(piece.tracks) == len(schema.tracks)
