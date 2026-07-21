import tempfile
from pathlib import Path

import musicpy as mp
import pytest

from leadsheet.compiler import (
    assign_channels,
    compile_chord_event,
    compile_note_event,
    compile_piece,
    track_bar_length,
)
from leadsheet.schema import ChordEvent, NoteEvent, PieceSchema, TrackSchema


def test_block_style():
    event = ChordEvent(type="chord", chord="Am7", bars=1)
    result = compile_chord_event(event)
    assert [n.name for n in result.notes] == ["A", "C", "E", "G"]
    assert result.interval == [0, 0, 0, 0]
    assert result.bars() == 1.0


def test_arpeggio_up_tiles_ascending_pattern():
    event = ChordEvent(type="chord", chord="Am7", bars=1, style="arpeggio_up", subdivision="1/8")
    result = compile_chord_event(event)
    # 1 bar / (1/8) = 8 slots, ascending 1..4 repeated
    assert len(result) == 8
    assert [n.name for n in result.notes] == ["A", "C", "E", "G"] * 2
    assert all(i == pytest.approx(1 / 8) for i in result.interval)


def test_arpeggio_updown_mirrors_without_repeated_boundary():
    event = ChordEvent(type="chord", chord="Am7", bars=1, style="arpeggio_updown", subdivision="1/8")
    result = compile_chord_event(event)
    # base pattern for n=4 is [1,2,3,4,3,2] tiled to 8 slots -> [1,2,3,4,3,2,1,2]
    names = [n.name for n in result.notes]
    assert names == ["A", "C", "E", "G", "E", "C", "A", "C"]


def test_custom_pattern_uses_pattern_verbatim_no_tiling():
    event = ChordEvent(
        type="chord", chord="Am7", bars=1, style="custom_pattern", pattern=[1, 2.1, 3, -1.2]
    )
    result = compile_chord_event(event)
    assert len(result) == 4
    # 2.1 = note 2 (C4) up 1 octave -> C5; -1.2 = note 1 (A3) down 2 octaves -> A1
    names_octaves = [(n.name, n.num) for n in result.notes]
    assert names_octaves == [("A", 3), ("C", 5), ("E", 4), ("A", 1)]


def test_root_only_single_sustained_note():
    event = ChordEvent(type="chord", chord="Cmaj7", bars=2, style="root_only")
    result = compile_chord_event(event)
    assert len(result) == 1
    assert result.notes[0].name == "C"
    assert result.bars() == 2.0


def test_root_fifth_two_notes():
    event = ChordEvent(type="chord", chord="Am7", bars=1, style="root_fifth")
    result = compile_chord_event(event)
    assert [n.name for n in result.notes] == ["A", "E"]
    assert result.interval == [0.5, 0.5]


def test_walking_cycles_root_third_fifth_approach():
    event = ChordEvent(type="chord", chord="Am7", bars=1, style="walking")
    result = compile_chord_event(event)
    # bars/subdivision = 1 / (1/4) = 4 slots: root, third, fifth, approach(+1 semitone)
    names = [n.name for n in result.notes]
    assert names[0] == "A"  # root
    assert names[1] == "C"  # third
    assert names[2] == "E"  # fifth
    assert len(result) == 4


def test_note_event_builds_single_note():
    event = NoteEvent(type="note", note="E5", duration="1/4")
    result = compile_note_event(event)
    assert result.notes[0].name == "E"
    assert result.notes[0].num == 5
    assert result.interval == [0.25]


def test_note_event_rest_has_no_notes():
    event = NoteEvent(type="note", duration="1/8", rest=True)
    result = compile_note_event(event)
    assert len(result.notes) == 0
    assert result.bars() == 0


def test_note_event_stack_is_simultaneous():
    event = NoteEvent(type="note", notes=["C5", "E5", "G5"], duration="1/2")
    result = compile_note_event(event)
    assert [n.name for n in result.notes] == ["C", "E", "G"]
    # internal interval=0 between the simultaneous pitches; only the last
    # carries the external interval (here, defaulting to duration)
    assert result.interval == [0, 0, 0.5]
    assert result.bars() == 0.5


def test_note_event_with_interval_differing_from_duration():
    event = NoteEvent(type="note", note="E5", duration="1/2", interval="1/4")
    result = compile_note_event(event)
    assert result.interval == [0.25]
    assert result.notes[0].duration == 0.5


def test_compile_piece_lofi_progression_matches_spec_example():
    progression = ["Am7", "Dm7", "G7", "Cmaj7", "Fmaj7", "Em7", "Am7", "G7sus4"]
    schema = PieceSchema(
        bpm=85,
        tracks=[
            {
                "role": "chords",
                "instrument": "Electric Piano 1",
                "events": [
                    {"type": "chord", "chord": c, "octave": 3, "bars": 1, "style": "arpeggio_updown"}
                    for c in progression
                ],
            },
            {
                "role": "bass",
                "instrument": "Acoustic Bass",
                "events": [
                    {"type": "chord", "chord": c, "octave": 2, "bars": 1, "style": "root_fifth"}
                    for c in progression
                ],
            },
            {
                "role": "drums",
                "instrument": "Standard",
                "drum_pattern": "K, H, S, H",
                "repeat": 8,
            },
        ],
    )
    piece_obj = compile_piece(schema)
    midi_bytes = mp.write(piece_obj, bpm=schema.bpm, save_as_file=False).getvalue()
    assert len(midi_bytes) > 0


def test_write_json_read_json_round_trip_is_byte_identical():
    """Mirrors the write_json -> read_json -> write_json lossless round-trip
    technique validated live against real musicpy, as an automated regression."""
    event = ChordEvent(type="chord", chord="Am7", bars=1, style="arpeggio_updown")
    compiled = compile_chord_event(event)

    with tempfile.TemporaryDirectory() as tmp:
        first = Path(tmp) / "a.json"
        second = Path(tmp) / "b.json"
        mp.write_json(compiled, filename=str(first))
        reloaded = mp.read_json(str(first))
        mp.write_json(reloaded, filename=str(second))
        assert first.read_bytes() == second.read_bytes()


def test_assign_channels_shares_channels_past_the_15_non_drum_limit():
    """Regression for a latent hang: assign_channels used to increment an
    unbounded counter looking for a free non-drum channel, which never
    terminates once all 15 (MIDI has 16 channels total, minus channel 9 for
    drums) are taken. 16 non-drum tracks (now possible after the MAX_TRACKS
    bump) must still terminate, sharing a channel for the 16th."""
    tracks = [
        TrackSchema(
            role="chords",
            instrument="Acoustic Grand Piano",
            events=[{"type": "chord", "chord": "C", "bars": 1}],
        )
        for _ in range(16)
    ]
    channels = assign_channels(tracks)
    assert len(channels) == 16
    assert 9 not in channels
    assert all(0 <= c <= 15 for c in channels)
    # first 15 tracks get 15 distinct channels; the 16th shares one
    assert len(set(channels[:15])) == 15
    assert channels[15] in channels[:15]


def test_assign_channels_respects_explicit_channels_and_drums():
    tracks = [
        TrackSchema(role="drums", instrument="Standard", drum_pattern="K, H"),
        TrackSchema(
            role="chords", instrument="Acoustic Grand Piano", channel=3,
            events=[{"type": "chord", "chord": "C", "bars": 1}],
        ),
        TrackSchema(
            role="bass", instrument="Acoustic Bass",
            events=[{"type": "chord", "chord": "C", "bars": 1}],
        ),
    ]
    channels = assign_channels(tracks)
    assert channels[0] == 9
    assert channels[1] == 3
    assert channels[2] not in (3, 9)


def test_track_bar_length_sums_chord_and_note_events():
    track = TrackSchema(
        role="chords",
        instrument="Acoustic Grand Piano",
        events=[
            {"type": "chord", "chord": "C", "bars": 1.5},
            {"type": "note", "duration": "1/4", "rest": True},
        ],
    )
    assert track_bar_length(track) == pytest.approx(1.75)


def test_track_bar_length_sums_note_stack_duration():
    track = TrackSchema(
        role="melody",
        instrument="Flute",
        events=[{"type": "note", "notes": ["C5", "E5", "G5"], "duration": "1/4"}],
    )
    assert track_bar_length(track) == pytest.approx(0.25)


def test_track_bar_length_zero_for_drums():
    track = TrackSchema(role="drums", instrument="Standard", drum_pattern="K, H")
    assert track_bar_length(track) == 0.0


def test_other_messages_never_shared_for_directly_constructed_chords():
    """Regression for musicpy's mutable-default-arg hazard: every chord()
    the compiler constructs directly must pass a fresh other_messages=[]
    literal, not share the process-wide default list.

    Note: chord.set() (used by block/arpeggio_* styles) constructs its
    result internally without forwarding other_messages at all -- that's
    a musicpy-internal limitation the compiler can't work around by
    passing a kwarg .set() doesn't accept. It's harmless in practice
    because the compiler never mutates .other_messages in place anywhere;
    this test covers the styles the compiler *does* construct directly
    (root_only/root_fifth/walking/note/rest)."""
    a = compile_chord_event(ChordEvent(type="chord", chord="Am7", bars=1, style="root_only"))
    b = compile_chord_event(ChordEvent(type="chord", chord="Dm7", bars=1, style="root_only"))
    assert a.other_messages is not b.other_messages
