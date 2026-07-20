from leadsheet.theory_check import validate


def test_lofi_progression_matches_with_zero_warnings():
    """The exact 8-chord progression validated live against real musicpy in
    the design session -- every chord should match with zero warnings."""
    progression = ["Am7", "Dm7", "G7", "Cmaj7", "Fmaj7", "Em7", "Am7", "G7sus4"]
    schema = {
        "bpm": 85,
        "tracks": [
            {
                "role": "chords",
                "instrument": "Electric Piano 1",
                "events": [
                    {"type": "chord", "chord": c, "bars": 1} for c in progression
                ],
            }
        ],
    }
    result = validate(schema)
    assert result.valid
    assert result.warnings == []
    assert len(result.detected_chords) == 8
    assert all(d["match"] for d in result.detected_chords)


def test_power_chord_produces_a_mismatch_warning():
    """A power chord (root+fifth only, no third) is detected by musicpy as
    an 'interval', not a 'chord' type -- a genuine, deterministic case
    where the theory-check should flag a mismatch rather than silently
    calling it a match."""
    schema = {
        "bpm": 100,
        "tracks": [
            {
                "role": "chords",
                "instrument": "Distortion Guitar",
                "events": [{"type": "chord", "chord": "C5", "bars": 1}],
            }
        ],
    }
    result = validate(schema)
    assert result.valid  # structurally fine -- this is a semantic warning, not an error
    assert len(result.warnings) == 1
    assert result.detected_chords[0]["match"] is False
    assert result.detected_chords[0]["intended"] == "C5"


def test_alias_spelling_difference_does_not_produce_a_false_warning():
    """'6' and 'add6' are aliases of the same chord family -- requesting one
    and having musicpy's detector report the other's canonical spelling
    should NOT be treated as a mismatch."""
    schema = {
        "bpm": 100,
        "tracks": [
            {
                "role": "chords",
                "instrument": "Acoustic Grand Piano",
                "events": [{"type": "chord", "chord": "C6", "bars": 1}],
            }
        ],
    }
    result = validate(schema)
    assert result.valid
    assert result.warnings == []
    assert result.detected_chords[0]["match"] is True


def test_invalid_schema_returns_errors_and_skips_semantic_checks():
    result = validate({"bpm": -1, "tracks": []})
    assert not result.valid
    assert result.errors
    assert result.warnings == []
    assert result.detected_chords == []
