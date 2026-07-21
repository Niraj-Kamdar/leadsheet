import pytest
from pydantic import ValidationError

from leadsheet import limits
from leadsheet.schema import PieceSchema


def _piece(**overrides):
    base = {
        "bpm": 100,
        "tracks": [
            {
                "role": "chords",
                "instrument": "Acoustic Grand Piano",
                "events": [{"type": "chord", "chord": "Am7", "bars": 1}],
            }
        ],
    }
    base.update(overrides)
    return base


def test_valid_piece_round_trips():
    PieceSchema(**_piece())


def test_bad_chord_name_suggests_correction():
    piece = _piece(
        tracks=[
            {
                "role": "chords",
                "instrument": "Acoustic Grand Piano",
                "events": [{"type": "chord", "chord": "FMaj7", "bars": 1}],
            }
        ]
    )
    with pytest.raises(ValidationError) as exc:
        PieceSchema(**piece)
    message = str(exc.value)
    assert "not a valid chord symbol" in message
    assert "Fmaj7" in message


def test_channel_9_on_non_drum_track_is_a_hard_error():
    piece = _piece(
        tracks=[
            {
                "role": "chords",
                "instrument": "Acoustic Grand Piano",
                "channel": 9,
                "events": [{"type": "chord", "chord": "Am7", "bars": 1}],
            }
        ]
    )
    with pytest.raises(ValidationError, match="channel 9 is reserved for drum tracks"):
        PieceSchema(**piece)


def test_missing_pattern_on_custom_pattern_style_is_a_hard_error():
    piece = _piece(
        tracks=[
            {
                "role": "chords",
                "instrument": "Acoustic Grand Piano",
                "events": [{"type": "chord", "chord": "Am7", "bars": 1, "style": "custom_pattern"}],
            }
        ]
    )
    with pytest.raises(ValidationError, match="pattern is required"):
        PieceSchema(**piece)


def test_pattern_forbidden_outside_custom_pattern_style():
    piece = _piece(
        tracks=[
            {
                "role": "chords",
                "instrument": "Acoustic Grand Piano",
                "events": [
                    {"type": "chord", "chord": "Am7", "bars": 1, "style": "block", "pattern": [1, 2]}
                ],
            }
        ]
    )
    with pytest.raises(ValidationError, match="pattern is only valid when"):
        PieceSchema(**piece)


def test_drum_track_requires_drum_pattern():
    piece = _piece(tracks=[{"role": "drums", "instrument": "Standard", "channel": 9}])
    with pytest.raises(ValidationError, match="drum_pattern is required"):
        PieceSchema(**piece)


def test_drum_track_forbids_events():
    piece = _piece(
        tracks=[
            {
                "role": "drums",
                "instrument": "Standard",
                "channel": 9,
                "drum_pattern": "K, H",
                "events": [{"type": "chord", "chord": "Am7", "bars": 1}],
            }
        ]
    )
    with pytest.raises(ValidationError, match="events must be absent"):
        PieceSchema(**piece)


def test_non_drum_track_requires_events():
    piece = _piece(tracks=[{"role": "chords", "instrument": "Acoustic Grand Piano"}])
    with pytest.raises(ValidationError, match="events must be non-empty"):
        PieceSchema(**piece)


def test_unknown_instrument_name_is_rejected():
    piece = _piece(
        tracks=[
            {
                "role": "chords",
                "instrument": "Not A Real Instrument",
                "events": [{"type": "chord", "chord": "Am7", "bars": 1}],
            }
        ]
    )
    with pytest.raises(ValidationError, match="not a known General MIDI instrument"):
        PieceSchema(**piece)


def test_drum_instrument_validated_against_drum_kits_not_gm_instruments():
    piece = _piece(
        tracks=[
            {
                "role": "drums",
                # a real GM instrument name, but not a drum-kit name
                "instrument": "Acoustic Grand Piano",
                "channel": 9,
                "drum_pattern": "K, H",
            }
        ]
    )
    with pytest.raises(ValidationError, match="not a known drum-kit name"):
        PieceSchema(**piece)


def test_invalid_fraction_string_is_rejected():
    piece = _piece(
        tracks=[
            {
                "role": "chords",
                "instrument": "Acoustic Grand Piano",
                "events": [
                    {"type": "chord", "chord": "Am7", "bars": 1, "subdivision": "not-a-fraction"}
                ],
            }
        ]
    )
    with pytest.raises(ValidationError, match="not a valid fraction"):
        PieceSchema(**piece)


def test_too_many_tracks_is_a_hard_error_with_actual_value():
    one_track = {
        "role": "chords",
        "instrument": "Acoustic Grand Piano",
        "events": [{"type": "chord", "chord": "Am7", "bars": 1}],
    }
    piece = _piece(tracks=[one_track] * (limits.MAX_TRACKS + 1))
    with pytest.raises(ValidationError, match=f"got {limits.MAX_TRACKS + 1}"):
        PieceSchema(**piece)


def test_over_limit_bars_is_a_hard_error_with_actual_value():
    piece = _piece(
        tracks=[
            {
                "role": "chords",
                "instrument": "Acoustic Grand Piano",
                "events": [
                    {"type": "chord", "chord": "Am7", "bars": limits.MAX_BARS_PER_TRACK + 1}
                ],
            }
        ]
    )
    with pytest.raises(ValidationError, match="exceeds MAX_BARS_PER_TRACK"):
        PieceSchema(**piece)


def test_expected_bars_must_be_positive():
    piece = _piece(
        tracks=[
            {
                "role": "chords",
                "instrument": "Acoustic Grand Piano",
                "expected_bars": 0,
                "events": [{"type": "chord", "chord": "Am7", "bars": 1}],
            }
        ]
    )
    with pytest.raises(ValidationError, match="greater than 0"):
        PieceSchema(**piece)


def test_expected_bars_defaults_to_none_and_is_not_checked_by_pydantic():
    # The actual expected_bars-vs-computed-length check lives in
    # theory_check.py -- PieceSchema itself just stores whatever value is
    # given, mismatched or not.
    piece = _piece(
        tracks=[
            {
                "role": "chords",
                "instrument": "Acoustic Grand Piano",
                "expected_bars": 999,
                "events": [{"type": "chord", "chord": "Am7", "bars": 1}],
            }
        ]
    )
    schema = PieceSchema(**piece)
    assert schema.tracks[0].expected_bars == 999


def test_note_event_requires_note_unless_rest():
    piece = _piece(
        tracks=[
            {
                "role": "melody",
                "instrument": "Flute",
                "events": [{"type": "note", "duration": "1/4"}],
            }
        ]
    )
    with pytest.raises(ValidationError, match="exactly one of rest, note, notes must be set"):
        PieceSchema(**piece)


def test_note_event_accepts_simultaneous_note_stack():
    piece = _piece(
        tracks=[
            {
                "role": "melody",
                "instrument": "Flute",
                "events": [{"type": "note", "notes": ["C5", "E5", "G5"], "duration": "1/2"}],
            }
        ]
    )
    schema = PieceSchema(**piece)
    assert schema.tracks[0].events[0].notes == ["C5", "E5", "G5"]


def test_note_event_rejects_simultaneous_note_and_notes():
    piece = _piece(
        tracks=[
            {
                "role": "melody",
                "instrument": "Flute",
                "events": [
                    {"type": "note", "note": "C5", "notes": ["E5", "G5"], "duration": "1/2"}
                ],
            }
        ]
    )
    with pytest.raises(ValidationError, match="exactly one of rest, note, notes must be set"):
        PieceSchema(**piece)
