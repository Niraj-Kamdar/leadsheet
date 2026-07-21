import pytest

from leadsheet import dsl

# ---------------------------------------------------------------------------
# Per line-kind tests (spec-2.md SS2.1-2.5)
# ---------------------------------------------------------------------------


def test_top_level_bpm_only():
    result = dsl.parse_dsl("bpm=120\nchords \"Piano\" block: C\n")
    assert result["bpm"] == 120
    assert "title" not in result
    assert "key" not in result


def test_top_level_with_title_and_key():
    result = dsl.parse_dsl('bpm=85 title="lofi study break" key="A minor"\nchords "Piano" block: C\n')
    assert result["bpm"] == 85
    assert result["title"] == "lofi study break"
    assert result["key"] == "A minor"


def test_top_level_key_order_independent():
    result = dsl.parse_dsl('key="A minor" title="x" bpm=85\nchords "Piano" block: C\n')
    assert result["bpm"] == 85
    assert result["title"] == "x"
    assert result["key"] == "A minor"


def test_track_header_inline_single_segment_with_modifiers():
    result = dsl.parse_dsl(
        'bpm=100\nchords "Acoustic Grand Piano" name="keys" start=2 vol=90 repeat=2 block subdiv=1/4: C G\n'
    )
    track = result["tracks"][0]
    assert track == {
        "role": "chords",
        "instrument": "Acoustic Grand Piano",
        "name": "keys",
        "start_bar": 2,
        "volume": 90,
        "repeat": 2,
        "events": [
            {"type": "chord", "chord": "C", "bars": 1, "style": "block", "subdivision": "1/4"},
            {"type": "chord", "chord": "G", "bars": 1, "style": "block", "subdivision": "1/4"},
        ],
    }


def test_track_header_bare_int_instrument():
    result = dsl.parse_dsl("bpm=100\nchords 5 block: C\n")
    assert result["tracks"][0]["instrument"] == 5


def test_track_header_no_modifiers_no_style_defaults_to_block():
    result = dsl.parse_dsl('bpm=100\nchords "Piano": C\n')
    assert result["tracks"][0]["events"] == [{"type": "chord", "chord": "C", "bars": 1}]


def test_segment_line_multi_segment_track():
    text = (
        'bpm=130\n'
        'chords "Distortion Guitar" name="rhythm":\n'
        '  custom_pattern pattern=[1,2] subdiv=1/8 oct=2: E5 G5\n'
        '  block subdiv=1/4 oct=2: F5 G5\n'
    )
    events = dsl.parse_dsl(text)["tracks"][0]["events"]
    assert events == [
        {"type": "chord", "chord": "E5", "bars": 1, "style": "custom_pattern", "octave": 2,
         "subdivision": "1/8", "pattern": [1, 2]},
        {"type": "chord", "chord": "G5", "bars": 1, "style": "custom_pattern", "octave": 2,
         "subdivision": "1/8", "pattern": [1, 2]},
        {"type": "chord", "chord": "F5", "bars": 1, "style": "block", "octave": 2, "subdivision": "1/4"},
        {"type": "chord", "chord": "G5", "bars": 1, "style": "block", "octave": 2, "subdivision": "1/4"},
    ]


def test_drum_line():
    result = dsl.parse_dsl('bpm=120\ndrums "Power Kit" name="drums" repeat=4: K, H, S, H\n')
    track = result["tracks"][0]
    assert track == {
        "role": "drums",
        "instrument": "Power Kit",
        "name": "drums",
        "repeat": 4,
        "drum_pattern": "K, H, S, H",
    }


def test_drum_line_normalizes_comma_spacing():
    result = dsl.parse_dsl('bpm=120\ndrums "Power Kit": K,H,S,H\n')
    assert result["tracks"][0]["drum_pattern"] == "K, H, S, H"


def test_drum_line_rest_token():
    result = dsl.parse_dsl('bpm=92\ndrums "TR-808 Kit": K, 0, K, S2\n')
    assert result["tracks"][0]["drum_pattern"] == "K, 0, K, S2"


def test_melody_notes_line():
    result = dsl.parse_dsl('bpm=100\nmelody "Violin" notes: E5@1/4 r@1/8 G5@1/4\n')
    assert result["tracks"][0]["events"] == [
        {"type": "note", "note": "E5", "duration": "1/4"},
        {"type": "note", "rest": True, "duration": "1/8"},
        {"type": "note", "note": "G5", "duration": "1/4"},
    ]


def test_melody_notes_segment_default_duration():
    result = dsl.parse_dsl('bpm=100\nmelody "Flute" notes dur=1/4: E5 r C5\n')
    assert result["tracks"][0]["events"] == [
        {"type": "note", "note": "E5", "duration": "1/4"},
        {"type": "note", "rest": True, "duration": "1/4"},
        {"type": "note", "note": "C5", "duration": "1/4"},
    ]


def test_melody_notes_per_token_override_wins_over_segment_default():
    result = dsl.parse_dsl('bpm=100\nmelody "Flute" notes dur=1/4: E5 C5@1/2\n')
    events = result["tracks"][0]["events"]
    assert events[0]["duration"] == "1/4"
    assert events[1]["duration"] == "1/2"
    assert "interval" not in events[1]


def test_melody_notes_int_segment_default_applies_only_without_override():
    result = dsl.parse_dsl('bpm=100\nmelody "Flute" notes dur=1/4 int=1/8: E5 C5@1/2\n')
    events = result["tracks"][0]["events"]
    assert events[0] == {"type": "note", "note": "E5", "duration": "1/4", "interval": "1/8"}
    # the token's own @ override sets duration==interval, superseding int=
    assert events[1] == {"type": "note", "note": "C5", "duration": "1/2"}


def test_melody_notes_vel_segment_default():
    result = dsl.parse_dsl('bpm=100\nmelody "Flute" notes dur=1/4 vel=70: E5 G5\n')
    events = result["tracks"][0]["events"]
    assert all(e["velocity"] == 70 for e in events)


def test_melody_notes_simultaneous_stack():
    result = dsl.parse_dsl('bpm=100\nmelody "Piano" notes dur=1/2: C5+E5+G5\n')
    assert result["tracks"][0]["events"] == [
        {"type": "note", "notes": ["C5", "E5", "G5"], "duration": "1/2"}
    ]


def test_melody_notes_stack_with_override():
    result = dsl.parse_dsl('bpm=100\nmelody "Piano" notes: C5+E5+G5@1/2\n')
    assert result["tracks"][0]["events"] == [
        {"type": "note", "notes": ["C5", "E5", "G5"], "duration": "1/2"}
    ]


def test_melody_notes_repeat_count_on_preceding_token():
    result = dsl.parse_dsl('bpm=100\nmelody "Flute" notes dur=1/8: E5 x3 G5\n')
    events = result["tracks"][0]["events"]
    assert [e["note"] for e in events] == ["E5", "E5", "E5", "G5"]
    assert events[0] is not events[1]  # independent dict copies


def test_melody_notes_repeat_count_works_on_a_stack():
    result = dsl.parse_dsl('bpm=100\nmelody "Piano" notes dur=1/4: C5+E5 x2\n')
    events = result["tracks"][0]["events"]
    assert [e["notes"] for e in events] == [["C5", "E5"], ["C5", "E5"]]


def test_melody_notes_can_be_a_segment_line():
    text = (
        'bpm=100\n'
        'melody "Flute":\n'
        '  block: C\n'
        '  notes dur=1/4: E5 G5\n'
    )
    events = dsl.parse_dsl(text)["tracks"][0]["events"]
    assert events[0]["type"] == "chord"
    assert events[1] == {"type": "note", "note": "E5", "duration": "1/4"}
    assert events[2] == {"type": "note", "note": "G5", "duration": "1/4"}


def test_melody_track_can_use_chord_list_segment():
    # Not all melody tracks use notes: -- genre-recipes.md's Chiptune and
    # EDM examples give melody-role tracks an ordinary chord-list segment
    # (arpeggiated) instead. See dsl.py's module docstring.
    result = dsl.parse_dsl('bpm=150\nmelody "Lead 1 (square)" arpeggio_up subdiv=1/16 oct=5: C Am\n')
    assert result["tracks"][0]["events"] == [
        {"type": "chord", "chord": "C", "bars": 1, "style": "arpeggio_up", "subdivision": "1/16", "octave": 5},
        {"type": "chord", "chord": "Am", "bars": 1, "style": "arpeggio_up", "subdivision": "1/16", "octave": 5},
    ]


def test_multiple_tracks_and_custom_role():
    result = dsl.parse_dsl(
        'bpm=100\nchords "Piano" block: C\ncustom "Guitar" vol=80 block: E\n'
    )
    assert [t["role"] for t in result["tracks"]] == ["chords", "custom"]
    assert result["tracks"][1]["volume"] == 80


# ---------------------------------------------------------------------------
# Sub-bar chords, rests, and the bars= assertion (orchestral-scoring fixes)
# ---------------------------------------------------------------------------


def test_chord_list_token_bars_suffix_decimal_and_fraction():
    result = dsl.parse_dsl('bpm=100\nchords "Piano" block: Am7*0.5 C*1/2 F*2\n')
    events = result["tracks"][0]["events"]
    assert [e["bars"] for e in events] == [0.5, 0.5, 2.0]


def test_chord_list_token_no_suffix_defaults_to_bars_1():
    result = dsl.parse_dsl('bpm=100\nchords "Piano" block: C\n')
    assert result["tracks"][0]["events"][0]["bars"] == 1


def test_chord_list_rest_token():
    result = dsl.parse_dsl('bpm=100\nchords "Piano" block: C r Am7\n')
    events = result["tracks"][0]["events"]
    assert events[1] == {"type": "note", "rest": True, "duration": 1}
    # rest doesn't pick up the segment's style/etc -- NoteEvent has no such fields
    assert events[0]["style"] == "block"
    assert "style" not in events[1]


def test_chord_list_rest_token_with_bars_suffix():
    result = dsl.parse_dsl('bpm=100\nchords "Piano" oct=2 subdiv=1/8: r*0.25 C\n')
    events = result["tracks"][0]["events"]
    assert events[0] == {"type": "note", "rest": True, "duration": 0.25}
    assert events[1]["octave"] == 2  # segment modifiers still apply to the real chord


def test_chord_list_bars_suffix_and_rest_work_in_multi_segment_tracks():
    text = (
        'bpm=100\n'
        'chords "Piano":\n'
        '  block: Am7*0.5 r*0.5\n'
        '  block: C\n'
    )
    events = dsl.parse_dsl(text)["tracks"][0]["events"]
    assert events == [
        {"type": "chord", "chord": "Am7", "bars": 0.5, "style": "block"},
        {"type": "note", "rest": True, "duration": 0.5},
        {"type": "chord", "chord": "C", "bars": 1, "style": "block"},
    ]


def test_error_bars_suffix_not_a_number():
    with pytest.raises(dsl.DslSyntaxError, match=r"line 2.*bars value.*not a number"):
        dsl.parse_dsl('bpm=100\nchords "Piano" block: C*abc\n')


def test_error_bars_suffix_missing_chord():
    with pytest.raises(dsl.DslSyntaxError, match=r"line 2.*missing a chord/rest before"):
        dsl.parse_dsl('bpm=100\nchords "Piano" block: *0.5\n')


def test_bars_header_modifier_maps_to_expected_bars():
    result = dsl.parse_dsl('bpm=100\nchords "Piano" bars=2 block: C G\n')
    assert result["tracks"][0]["expected_bars"] == 2


def test_error_bars_modifier_rejected_on_drums():
    with pytest.raises(dsl.DslSyntaxError, match=r"line 2.*bars=.*drums track"):
        dsl.parse_dsl('bpm=100\ndrums "Power Kit" bars=4: K, H, S, H\n')


# ---------------------------------------------------------------------------
# define/use macros
# ---------------------------------------------------------------------------


def test_macro_chord_list_kind_used_inline():
    text = (
        'bpm=100\n'
        'define riff block subdiv=1/4 oct=2: C G\n'
        'chords "Distortion Guitar" use: riff\n'
    )
    events = dsl.parse_dsl(text)["tracks"][0]["events"]
    assert events == [
        {"type": "chord", "chord": "C", "bars": 1, "style": "block", "octave": 2, "subdivision": "1/4"},
        {"type": "chord", "chord": "G", "bars": 1, "style": "block", "octave": 2, "subdivision": "1/4"},
    ]


def test_macro_used_as_a_segment_line_among_others():
    text = (
        'bpm=100\n'
        'define riff: C G\n'
        'chords "Piano":\n'
        '  block: Am7\n'
        '  use: riff\n'
    )
    events = dsl.parse_dsl(text)["tracks"][0]["events"]
    assert [e["chord"] for e in events] == ["Am7", "C", "G"]


def test_macro_use_repeat_count():
    text = 'bpm=100\ndefine riff: C G\nchords "Piano" use: riff x3\n'
    events = dsl.parse_dsl(text)["tracks"][0]["events"]
    assert [e["chord"] for e in events] == ["C", "G", "C", "G", "C", "G"]


def test_macro_use_produces_independent_dict_copies():
    text = 'bpm=100\ndefine riff: C\nchords "Piano" use: riff x2\n'
    events = dsl.parse_dsl(text)["tracks"][0]["events"]
    assert events[0] is not events[1]
    events[0]["chord"] = "mutated"
    assert events[1]["chord"] == "C"


def test_macro_notes_kind_reused_on_two_tracks():
    text = (
        'bpm=100\n'
        'define motif notes dur=1: C4 Eb4 G4\n'
        'melody "Trumpet" name="brass" start=16 use: motif\n'
        'melody "Violin" name="strings" start=32 use: motif x2\n'
    )
    tracks = dsl.parse_dsl(text)["tracks"]
    assert [e["note"] for e in tracks[0]["events"]] == ["C4", "Eb4", "G4"]
    assert [e["note"] for e in tracks[1]["events"]] == ["C4", "Eb4", "G4", "C4", "Eb4", "G4"]


def test_use_transpose_shifts_note_pitches():
    text = 'bpm=100\ndefine motif notes dur=1/4: E5 G5\nmelody "Violin" use: motif transpose=-3\n'
    events = dsl.parse_dsl(text)["tracks"][0]["events"]
    assert [e["note"] for e in events] == ["C#5", "E5"]


def test_use_transpose_crosses_octave_boundary():
    text = 'bpm=100\ndefine motif notes dur=1/4: B4\nmelody "Violin" use: motif transpose=2\n'
    events = dsl.parse_dsl(text)["tracks"][0]["events"]
    assert events[0]["note"] == "C#5"


def test_use_transpose_shifts_chord_root_and_octave():
    text = 'bpm=100\ndefine riff: B\nchords "Piano" use: riff transpose=2\n'
    events = dsl.parse_dsl(text)["tracks"][0]["events"]
    assert events[0]["chord"] == "C#"
    assert events[0]["octave"] == 4  # default octave 3, crosses up by 1


def test_use_transpose_shifts_note_stack():
    text = 'bpm=100\ndefine motif notes dur=1/2: C5+E5+G5\nmelody "Piano" use: motif transpose=2\n'
    events = dsl.parse_dsl(text)["tracks"][0]["events"]
    assert events[0]["notes"] == ["D5", "F#5", "A5"]


def test_use_vel_overrides_macro_velocity():
    text = 'bpm=100\ndefine motif notes dur=1/4: E5 G5\nmelody "Violin" use: motif vel=70\n'
    events = dsl.parse_dsl(text)["tracks"][0]["events"]
    assert all(e["velocity"] == 70 for e in events)


def test_use_transpose_and_vel_combine_with_repeat():
    text = 'bpm=100\ndefine motif notes dur=1/4: E5\nmelody "Violin" use: motif x2 transpose=1 vel=90\n'
    events = dsl.parse_dsl(text)["tracks"][0]["events"]
    assert [e["note"] for e in events] == ["F5", "F5"]
    assert all(e["velocity"] == 90 for e in events)


def test_error_use_transpose_on_drum_macro_rejected():
    text = 'bpm=100\ndefine groove: K, H\ndrums "Power Kit" use: groove transpose=2\n'
    with pytest.raises(dsl.DslSyntaxError, match=r"line 3.*transpose=/vel=.*aren't valid on a drum"):
        dsl.parse_dsl(text)


def test_macro_notes_kind():
    text = 'bpm=100\ndefine phrase notes: E5@1/4 r@1/8\nmelody "Violin" use: phrase\n'
    events = dsl.parse_dsl(text)["tracks"][0]["events"]
    assert events == [
        {"type": "note", "note": "E5", "duration": "1/4"},
        {"type": "note", "rest": True, "duration": "1/8"},
    ]


def test_macro_drum_kind():
    text = 'bpm=100\ndefine groove: K, H, S, H\ndrums "Power Kit" use: groove x2\n'
    track = dsl.parse_dsl(text)["tracks"][0]
    assert track["drum_pattern"] == "K, H, S, H, K, H, S, H"


def test_macro_drum_kind_inferred_from_comma_no_style_prefix():
    text = 'bpm=100\ndefine groove: K, 0, K, S2\ndrums "TR-808 Kit" use: groove\n'
    assert dsl.parse_dsl(text)["tracks"][0]["drum_pattern"] == "K, 0, K, S2"


def test_error_undefined_macro():
    with pytest.raises(dsl.DslSyntaxError, match=r"line 2.*undefined macro 'nope'"):
        dsl.parse_dsl('bpm=100\nchords "Piano" use: nope\n')


def test_error_macro_kind_mismatch():
    text = 'bpm=100\ndefine groove: K, H\nchords "Piano" use: groove\n'
    with pytest.raises(dsl.DslSyntaxError, match=r"line 3.*'drum'-kind macro.*'events'-kind"):
        dsl.parse_dsl(text)


def test_error_nested_macro_rejected():
    text = 'bpm=100\ndefine base: C G\ndefine wrapper use: base\n'
    with pytest.raises(dsl.DslSyntaxError, match=r"line 3.*no nested macros"):
        dsl.parse_dsl(text)


def test_error_duplicate_macro_name():
    text = 'bpm=100\ndefine riff: C\ndefine riff: G\n'
    with pytest.raises(dsl.DslSyntaxError, match=r"line 3.*already defined"):
        dsl.parse_dsl(text)


def test_error_invalid_macro_name():
    with pytest.raises(dsl.DslSyntaxError, match=r"line 2.*not a valid macro name"):
        dsl.parse_dsl('bpm=100\ndefine 1bad: C\n')


def test_error_define_inside_open_track():
    text = 'bpm=100\nchords "Piano":\n  define riff: C\n'
    with pytest.raises(dsl.DslSyntaxError, match=r"line 3.*'define' can't appear inside an open track"):
        dsl.parse_dsl(text)


def test_error_use_repeat_count_malformed():
    text = 'bpm=100\ndefine riff: C\nchords "Piano" use: riff x0\n'
    with pytest.raises(dsl.DslSyntaxError, match=r"line 3.*repeat count must be >= 1"):
        dsl.parse_dsl(text)


def test_error_misplaced_colon_after_macro_name_gives_actionable_message():
    """The easy-to-make mistake: `define name: notes: ...` puts the ':'
    right after the name, which becomes the terminator before 'notes:' is
    ever seen -- must not be silently misclassified as a drum-kind macro
    just because the leftover text contains commas."""
    text = 'bpm=100\ndefine motif: notes: C4@1/4, D4@1/4\n'
    with pytest.raises(dsl.DslSyntaxError, match=r"line 2.*'notes:'.*already ended the header"):
        dsl.parse_dsl(text)


# ---------------------------------------------------------------------------
# section / use section
# ---------------------------------------------------------------------------

CHORUS_SECTION = (
    'bpm=100\n'
    'section chorus:\n'
    '  chords "Electric Piano 1" block: F C\n'
    '  bass "Acoustic Bass" root_fifth oct=2: F C\n'
    '  drums "Standard" repeat=2: K, H, S, H\n'
    '  melody "Flute" notes dur=1/4: F5 A5\n'
    'use section chorus start=8\n'
)


def test_use_section_appends_every_fragment_offset_by_start():
    tracks = dsl.parse_dsl(CHORUS_SECTION)["tracks"]
    assert len(tracks) == 4
    assert [t["role"] for t in tracks] == ["chords", "bass", "drums", "melody"]
    assert all(t["start_bar"] == 8 for t in tracks)
    assert tracks[0]["events"][0]["chord"] == "F"


def test_use_section_can_be_invoked_more_than_once():
    text = CHORUS_SECTION + 'use section chorus start=24\n'
    tracks = dsl.parse_dsl(text)["tracks"]
    assert len(tracks) == 8
    assert [t["start_bar"] for t in tracks] == [8, 8, 8, 8, 24, 24, 24, 24]


def test_use_section_offset_adds_to_fragments_own_start():
    text = (
        'bpm=100\n'
        'section intro:\n'
        '  chords "Piano" start=1 block: C\n'
        'use section intro start=8\n'
    )
    tracks = dsl.parse_dsl(text)["tracks"]
    assert tracks[0]["start_bar"] == 9


def test_use_section_produces_independent_copies():
    text = CHORUS_SECTION + 'use section chorus start=24\n'
    tracks = dsl.parse_dsl(text)["tracks"]
    assert tracks[0] is not tracks[4]
    tracks[0]["events"][0]["chord"] = "mutated"
    assert tracks[4]["events"][0]["chord"] == "F"


def test_error_undefined_section():
    with pytest.raises(dsl.DslSyntaxError, match=r"line 2.*undefined section 'nope'"):
        dsl.parse_dsl('bpm=100\nuse section nope start=8\n')


def test_error_use_section_missing_start():
    text = 'bpm=100\nsection intro:\n  chords "Piano" block: C\nuse section intro\n'
    with pytest.raises(dsl.DslSyntaxError, match=r"line 4.*requires start="):
        dsl.parse_dsl(text)


def test_error_section_with_no_fragments():
    with pytest.raises(dsl.DslSyntaxError, match=r"line 2.*no track fragments"):
        dsl.parse_dsl('bpm=100\nsection empty:\nuse section empty start=8\n')


def test_error_section_rejects_multi_segment_fragment():
    text = (
        'bpm=100\n'
        'section intro:\n'
        '  chords "Piano":\n'
        '  block: C\n'
    )
    with pytest.raises(dsl.DslSyntaxError, match=r"line 3.*multi-segment tracks aren't supported"):
        dsl.parse_dsl(text)


def test_error_duplicate_section_name():
    text = (
        'bpm=100\n'
        'section a:\n'
        '  chords "Piano" block: C\n'
        'section a:\n'
        '  chords "Piano" block: G\n'
    )
    with pytest.raises(dsl.DslSyntaxError, match=r"line 4.*already defined"):
        dsl.parse_dsl(text)


def test_error_section_header_with_trailing_content():
    with pytest.raises(dsl.DslSyntaxError, match=r"line 2.*nothing.*after the colon"):
        dsl.parse_dsl('bpm=100\nsection chorus: extra\n')


# ---------------------------------------------------------------------------
# Syntax-error cases
# ---------------------------------------------------------------------------


def test_error_first_line_not_bpm():
    with pytest.raises(dsl.DslSyntaxError, match=r"line 1.*bpm="):
        dsl.parse_dsl('title="x"\nchords "Piano" block: C\n')


def test_error_empty_input():
    with pytest.raises(dsl.DslSyntaxError, match="empty input"):
        dsl.parse_dsl("\n\n   \n")


def test_error_unrecognized_line_with_no_open_track():
    with pytest.raises(dsl.DslSyntaxError, match=r"line 2.*unrecognized line"):
        dsl.parse_dsl('bpm=100\nsomething weird\n')


def test_error_track_header_missing_instrument():
    with pytest.raises(dsl.DslSyntaxError, match=r"line 2.*missing an instrument"):
        dsl.parse_dsl("bpm=100\nchords\n")


def test_error_missing_colon_in_header():
    with pytest.raises(dsl.DslSyntaxError, match=r"line 2.*':'"):
        dsl.parse_dsl('bpm=100\nchords "Piano" block\n')


def test_error_unrecognized_modifier_key():
    with pytest.raises(dsl.DslSyntaxError, match=r"line 2.*bogus"):
        dsl.parse_dsl('bpm=100\nchords "Piano" bogus=1: C\n')


def test_error_unrecognized_style_token():
    with pytest.raises(dsl.DslSyntaxError, match=r"line 2.*not_a_style"):
        dsl.parse_dsl('bpm=100\nchords "Piano" not_a_style: C\n')


def test_error_header_mod_on_segment_line():
    text = 'bpm=100\nchords "Piano":\n  name="x" block: C\n'
    with pytest.raises(dsl.DslSyntaxError, match=r"line 3.*only valid on a track header"):
        dsl.parse_dsl(text)


def test_error_segment_line_empty_chord_list():
    text = 'bpm=100\nchords "Piano":\n  block:\n'
    with pytest.raises(dsl.DslSyntaxError, match=r"line 3.*no chord list"):
        dsl.parse_dsl(text)


def test_error_drums_missing_token_list():
    with pytest.raises(dsl.DslSyntaxError, match=r"line 2.*drum-token list"):
        dsl.parse_dsl('bpm=100\ndrums "Power Kit":\n')


def test_error_drums_with_style_modifier():
    with pytest.raises(dsl.DslSyntaxError, match=r"line 2.*don't take"):
        dsl.parse_dsl('bpm=100\ndrums "Power Kit" block: K, H\n')


def test_error_raw_is_no_longer_recognized():
    with pytest.raises(dsl.DslSyntaxError, match=r"line 2.*unrecognized token 'raw'"):
        dsl.parse_dsl('bpm=100\nmelody "Violin" raw: E5[.4;.4]\n')


def test_error_notes_token_missing_at_sign_and_no_segment_default():
    with pytest.raises(dsl.DslSyntaxError, match=r"line 2.*E5.*no segment dur="):
        dsl.parse_dsl('bpm=100\nmelody "Violin" notes: E5\n')


def test_error_notes_missing_content():
    with pytest.raises(dsl.DslSyntaxError, match=r"line 2.*requires at least one note/rest/stack token"):
        dsl.parse_dsl('bpm=100\nmelody "Violin" notes:\n')


def test_error_notes_dur_not_valid_on_chord_list_segment():
    with pytest.raises(dsl.DslSyntaxError, match=r"line 2.*dur=.*isn't valid on a chord-list"):
        dsl.parse_dsl('bpm=100\nchords "Piano" dur=1/4: C\n')


def test_error_chord_style_not_valid_on_notes_segment():
    with pytest.raises(dsl.DslSyntaxError, match=r"line 2.*can't be combined with a style"):
        dsl.parse_dsl('bpm=100\nmelody "Violin" block notes dur=1/4: E5\n')


def test_error_oct_not_valid_on_notes_segment():
    with pytest.raises(dsl.DslSyntaxError, match=r"line 2.*oct=.*isn't valid on a notes:"):
        dsl.parse_dsl('bpm=100\nmelody "Violin" notes dur=1/4 oct=5: E5\n')


def test_error_notes_repeat_with_no_preceding_token():
    with pytest.raises(dsl.DslSyntaxError, match=r"line 2.*no preceding note/rest/stack"):
        dsl.parse_dsl('bpm=100\nmelody "Violin" notes dur=1/4: x2\n')


def test_error_notes_malformed_stack():
    with pytest.raises(dsl.DslSyntaxError, match=r"line 2.*malformed note stack"):
        dsl.parse_dsl('bpm=100\nmelody "Violin" notes dur=1/4: C5+\n')


def test_error_pattern_not_bracketed():
    with pytest.raises(dsl.DslSyntaxError, match=r"line 2.*bracketed list"):
        dsl.parse_dsl('bpm=100\nchords "Piano" custom_pattern pattern=1,2: C\n')


def test_error_unterminated_quote():
    with pytest.raises(dsl.DslSyntaxError, match="unterminated quoted string"):
        dsl.parse_dsl('bpm=100\nchords "Piano block: C\n')


# ---------------------------------------------------------------------------
# Round-trip equivalence: every worked example in the repo, transcribed to
# B2, must parse into exactly the same dict as the existing JSON literal
# (spec-2.md SS6). Expected dicts are transcribed verbatim from SKILL.md /
# references/genre-recipes.md.
# ---------------------------------------------------------------------------

LOFI_B2 = """\
bpm=85 title="lofi study break" key="A minor"
chords "Electric Piano 1" name="chords" arpeggio_updown oct=3: Am7 Dm7 G7 Cmaj7 Fmaj7 Em7 Am7 G7sus4
bass "Acoustic Bass" name="bass" root_fifth oct=2: Am7 Dm7 G7 Cmaj7 Fmaj7 Em7 Am7 G7sus4
melody "Flute" name="melody" notes dur=1/4: E5 r C5 D5 E5@1/2 r A4 C5 B4@1/2 r@1/2 G4 A4 B4 C5@1/2 r@1/2 A4@1/2 G4@1/2 E4@1/2
drums "Standard" name="drums" repeat=8: K, H, S, H
"""

LOFI_EXPECTED = {
    "title": "lofi study break",
    "bpm": 85,
    "key": "A minor",
    "tracks": [
        {
            "name": "chords",
            "role": "chords",
            "instrument": "Electric Piano 1",
            "events": [
                {"type": "chord", "chord": c, "octave": 3, "bars": 1, "style": "arpeggio_updown"}
                for c in ["Am7", "Dm7", "G7", "Cmaj7", "Fmaj7", "Em7", "Am7", "G7sus4"]
            ],
        },
        {
            "name": "bass",
            "role": "bass",
            "instrument": "Acoustic Bass",
            "events": [
                {"type": "chord", "chord": c, "octave": 2, "bars": 1, "style": "root_fifth"}
                for c in ["Am7", "Dm7", "G7", "Cmaj7", "Fmaj7", "Em7", "Am7", "G7sus4"]
            ],
        },
        {
            "name": "melody",
            "role": "melody",
            "instrument": "Flute",
            "events": [
                {"type": "note", "note": "E5", "duration": "1/4"},
                {"type": "note", "rest": True, "duration": "1/4"},
                {"type": "note", "note": "C5", "duration": "1/4"},
                {"type": "note", "note": "D5", "duration": "1/4"},
                {"type": "note", "note": "E5", "duration": "1/2"},
                {"type": "note", "rest": True, "duration": "1/4"},
                {"type": "note", "note": "A4", "duration": "1/4"},
                {"type": "note", "note": "C5", "duration": "1/4"},
                {"type": "note", "note": "B4", "duration": "1/2"},
                {"type": "note", "rest": True, "duration": "1/2"},
                {"type": "note", "note": "G4", "duration": "1/4"},
                {"type": "note", "note": "A4", "duration": "1/4"},
                {"type": "note", "note": "B4", "duration": "1/4"},
                {"type": "note", "note": "C5", "duration": "1/2"},
                {"type": "note", "rest": True, "duration": "1/2"},
                {"type": "note", "note": "A4", "duration": "1/2"},
                {"type": "note", "note": "G4", "duration": "1/2"},
                {"type": "note", "note": "E4", "duration": "1/2"},
            ],
        },
        {
            "name": "drums",
            "role": "drums",
            "instrument": "Standard",
            "drum_pattern": "K, H, S, H",
            "repeat": 8,
        },
    ],
}

CUSTOM_PATTERN_REST_B2 = """\
bpm=100
chords "Electric Piano 1" custom_pattern pattern=[1,2,3,4,3.1,2.1,1.1] subdiv=1/8: Cmaj7
melody "Violin" notes: E5@1/4 r@1/8 G5@1/4
"""

CUSTOM_PATTERN_REST_EXPECTED = {
    "bpm": 100,
    "tracks": [
        {
            "role": "chords",
            "instrument": "Electric Piano 1",
            "events": [
                {
                    "type": "chord", "chord": "Cmaj7", "bars": 1, "style": "custom_pattern",
                    "pattern": [1, 2, 3, 4, 3.1, 2.1, 1.1],
                    "subdivision": "1/8",
                }
            ],
        },
        {
            "role": "melody",
            "instrument": "Violin",
            "events": [
                {"type": "note", "note": "E5", "duration": "1/4"},
                {"type": "note", "duration": "1/8", "rest": True},
                {"type": "note", "note": "G5", "duration": "1/4"},
            ],
        },
    ],
}

POP_B2 = """\
bpm=118
chords "Acoustic Grand Piano" block subdiv=1/4: C G Am F
bass "Electric Bass (finger)" walking oct=2: C G Am F
"""

POP_EXPECTED = {
    "bpm": 118,
    "tracks": [
        {
            "role": "chords",
            "instrument": "Acoustic Grand Piano",
            "events": [
                {"type": "chord", "chord": c, "bars": 1, "style": "block", "subdivision": "1/4"}
                for c in ["C", "G", "Am", "F"]
            ],
        },
        {
            "role": "bass",
            "instrument": "Electric Bass (finger)",
            "events": [
                {"type": "chord", "chord": c, "octave": 2, "bars": 1, "style": "walking"}
                for c in ["C", "G", "Am", "F"]
            ],
        },
    ],
}

ROCK_B2 = """\
bpm=138
chords "Overdriven Guitar" name="rhythm guitar" block subdiv=1/8 oct=2: A5 D5 E5 D5
bass "Electric Bass (pick)" name="bass" walking oct=1: A5 D5 E5 D5
drums "Power Kit" name="drums" repeat=4: K, H, S, H, K, H, S, H
"""

ROCK_EXPECTED = {
    "bpm": 138,
    "tracks": [
        {
            "name": "rhythm guitar",
            "role": "chords",
            "instrument": "Overdriven Guitar",
            "events": [
                {"type": "chord", "chord": c, "octave": 2, "bars": 1, "style": "block", "subdivision": "1/8"}
                for c in ["A5", "D5", "E5", "D5"]
            ],
        },
        {
            "name": "bass",
            "role": "bass",
            "instrument": "Electric Bass (pick)",
            "events": [
                {"type": "chord", "chord": c, "octave": 1, "bars": 1, "style": "walking"}
                for c in ["A5", "D5", "E5", "D5"]
            ],
        },
        {
            "name": "drums",
            "role": "drums",
            "instrument": "Power Kit",
            "drum_pattern": "K, H, S, H, K, H, S, H",
            "repeat": 4,
        },
    ],
}

METAL_B2 = """\
bpm=130
chords "Distortion Guitar" name="rhythm guitar":
  custom_pattern pattern=[1,2,1,1,2,1,1,2] subdiv=1/8 oct=2: E5 G5 A5 C5 E5 G5 A5 C5
  block subdiv=1/4 oct=2: F5(+octave) G5(+octave) C5(+octave) G5(+octave)
custom "Distortion Guitar" name="rhythm guitar (doubled low)" vol=90:
  custom_pattern pattern=[1,2,1,1,2,1,1,2] subdiv=1/8 oct=1: E5 G5 A5 C5 E5 G5 A5 C5
  block subdiv=1/4 oct=1: F5(+octave) G5(+octave) C5(+octave) G5(+octave)
melody "Electric Guitar (clean)" name="lead" start=8 notes dur=1: E5 D5 C5 D5
bass "Electric Bass (pick)" name="bass" root_only oct=1: E5 G5 A5 C5 E5 G5 A5 C5 F5 G5 C5 G5
drums "Power Kit" name="verse drums" repeat=8: K, H, S, H, K, K, S, H
drums "Power Kit" name="chorus drums" start=8 repeat=2: K, H, S, H, K, H, S, H, K, H, S, H, K, S2, S2, S2
"""

_METAL_PATTERN = [1, 2, 1, 1, 2, 1, 1, 2]
_METAL_CHUG_CHORDS = ["E5", "G5", "A5", "C5", "E5", "G5", "A5", "C5"]
_METAL_RING_CHORDS = ["F5(+octave)", "G5(+octave)", "C5(+octave)", "G5(+octave)"]


def _metal_rhythm_events(octave):
    return [
        {
            "type": "chord", "chord": c, "octave": octave, "bars": 1, "style": "custom_pattern",
            "pattern": _METAL_PATTERN, "subdivision": "1/8",
        }
        for c in _METAL_CHUG_CHORDS
    ] + [
        {"type": "chord", "chord": c, "octave": octave, "bars": 1, "style": "block", "subdivision": "1/4"}
        for c in _METAL_RING_CHORDS
    ]


METAL_EXPECTED = {
    "bpm": 130,
    "tracks": [
        {
            "name": "rhythm guitar",
            "role": "chords",
            "instrument": "Distortion Guitar",
            "events": _metal_rhythm_events(2),
        },
        {
            "name": "rhythm guitar (doubled low)",
            "role": "custom",
            "instrument": "Distortion Guitar",
            "volume": 90,
            "events": _metal_rhythm_events(1),
        },
        {
            "name": "lead",
            "role": "melody",
            "instrument": "Electric Guitar (clean)",
            "start_bar": 8,
            "events": [
                {"type": "note", "note": "E5", "duration": "1"},
                {"type": "note", "note": "D5", "duration": "1"},
                {"type": "note", "note": "C5", "duration": "1"},
                {"type": "note", "note": "D5", "duration": "1"},
            ],
        },
        {
            "name": "bass",
            "role": "bass",
            "instrument": "Electric Bass (pick)",
            "events": [
                {"type": "chord", "chord": c, "octave": 1, "bars": 1, "style": "root_only"}
                for c in ["E5", "G5", "A5", "C5", "E5", "G5", "A5", "C5", "F5", "G5", "C5", "G5"]
            ],
        },
        {
            "name": "verse drums",
            "role": "drums",
            "instrument": "Power Kit",
            "drum_pattern": "K, H, S, H, K, K, S, H",
            "repeat": 8,
        },
        {
            "name": "chorus drums",
            "role": "drums",
            "instrument": "Power Kit",
            "start_bar": 8,
            "drum_pattern": "K, H, S, H, K, H, S, H, K, H, S, H, K, S2, S2, S2",
            "repeat": 2,
        },
    ],
}

CHIPTUNE_B2 = """\
bpm=150
melody "Lead 1 (square)" name="lead" arpeggio_up subdiv=1/16 oct=5: C Am F G
bass "Lead 2 (sawtooth)" name="bass" root_only oct=3: C Am F G
drums "Electronic Kit" name="drums" repeat=4: K, H, S, H
"""

CHIPTUNE_EXPECTED = {
    "bpm": 150,
    "tracks": [
        {
            "name": "lead",
            "role": "melody",
            "instrument": "Lead 1 (square)",
            "events": [
                {"type": "chord", "chord": c, "octave": 5, "bars": 1, "style": "arpeggio_up", "subdivision": "1/16"}
                for c in ["C", "Am", "F", "G"]
            ],
        },
        {
            "name": "bass",
            "role": "bass",
            "instrument": "Lead 2 (sawtooth)",
            "events": [
                {"type": "chord", "chord": c, "octave": 3, "bars": 1, "style": "root_only"}
                for c in ["C", "Am", "F", "G"]
            ],
        },
        {
            "name": "drums",
            "role": "drums",
            "instrument": "Electronic Kit",
            "drum_pattern": "K, H, S, H",
            "repeat": 4,
        },
    ],
}

ACOUSTIC_B2 = """\
bpm=96
chords "Acoustic Guitar (steel)" name="guitar" custom_pattern pattern=[1,3,2,3,1,3,2,3] subdiv=1/8 oct=3: C G Am F
"""

ACOUSTIC_EXPECTED = {
    "bpm": 96,
    "tracks": [
        {
            "name": "guitar",
            "role": "chords",
            "instrument": "Acoustic Guitar (steel)",
            "events": [
                {
                    "type": "chord", "chord": c, "octave": 3, "bars": 1, "style": "custom_pattern",
                    "pattern": [1, 3, 2, 3, 1, 3, 2, 3], "subdivision": "1/8",
                }
                for c in ["C", "G", "Am", "F"]
            ],
        },
    ],
}

REGGAETON_B2 = """\
bpm=92
chords "Pad 3 (polysynth)" name="chords" block subdiv=1/4 oct=4: Am F C G
bass "Synth Bass 1" name="bass" root_only oct=2: Am F C G
drums "TR-808 Kit" name="dembow" repeat=4: K, 0, K, S2, 0, K, 0, S2
"""

REGGAETON_EXPECTED = {
    "bpm": 92,
    "tracks": [
        {
            "name": "chords",
            "role": "chords",
            "instrument": "Pad 3 (polysynth)",
            "events": [
                {"type": "chord", "chord": c, "octave": 4, "bars": 1, "style": "block", "subdivision": "1/4"}
                for c in ["Am", "F", "C", "G"]
            ],
        },
        {
            "name": "bass",
            "role": "bass",
            "instrument": "Synth Bass 1",
            "events": [
                {"type": "chord", "chord": c, "octave": 2, "bars": 1, "style": "root_only"}
                for c in ["Am", "F", "C", "G"]
            ],
        },
        {
            "name": "dembow",
            "role": "drums",
            "instrument": "TR-808 Kit",
            "drum_pattern": "K, 0, K, S2, 0, K, 0, S2",
            "repeat": 4,
        },
    ],
}

EDM_B2 = """\
bpm=128
chords "Pad 3 (polysynth)" name="pad" block subdiv=1/8 oct=4: Am9 Fmaj9 C G
melody "Lead 2 (sawtooth)" name="lead" arpeggio_updown subdiv=1/16 oct=5: Am F C G
bass "Synth Bass 2" name="bass" root_only oct=2: Am F C G
drums "Electronic Kit" name="drums" repeat=4: K, H, H, H, K, H, OH, H
"""

EDM_EXPECTED = {
    "bpm": 128,
    "tracks": [
        {
            "name": "pad",
            "role": "chords",
            "instrument": "Pad 3 (polysynth)",
            "events": [
                {"type": "chord", "chord": c, "octave": 4, "bars": 1, "style": "block", "subdivision": "1/8"}
                for c in ["Am9", "Fmaj9", "C", "G"]
            ],
        },
        {
            "name": "lead",
            "role": "melody",
            "instrument": "Lead 2 (sawtooth)",
            "events": [
                {"type": "chord", "chord": c, "octave": 5, "bars": 1, "style": "arpeggio_updown", "subdivision": "1/16"}
                for c in ["Am", "F", "C", "G"]
            ],
        },
        {
            "name": "bass",
            "role": "bass",
            "instrument": "Synth Bass 2",
            "events": [
                {"type": "chord", "chord": c, "octave": 2, "bars": 1, "style": "root_only"}
                for c in ["Am", "F", "C", "G"]
            ],
        },
        {
            "name": "drums",
            "role": "drums",
            "instrument": "Electronic Kit",
            "drum_pattern": "K, H, H, H, K, H, OH, H",
            "repeat": 4,
        },
    ],
}

CORPUS = [
    ("lofi", LOFI_B2, LOFI_EXPECTED),
    ("custom_pattern_rest", CUSTOM_PATTERN_REST_B2, CUSTOM_PATTERN_REST_EXPECTED),
    ("pop", POP_B2, POP_EXPECTED),
    ("rock", ROCK_B2, ROCK_EXPECTED),
    ("metal", METAL_B2, METAL_EXPECTED),
    ("chiptune", CHIPTUNE_B2, CHIPTUNE_EXPECTED),
    ("acoustic", ACOUSTIC_B2, ACOUSTIC_EXPECTED),
    ("reggaeton", REGGAETON_B2, REGGAETON_EXPECTED),
    ("edm", EDM_B2, EDM_EXPECTED),
]


@pytest.mark.parametrize("name,b2_text,expected", CORPUS, ids=[c[0] for c in CORPUS])
def test_corpus_round_trip(name, b2_text, expected):
    assert dsl.parse_dsl(b2_text) == expected


@pytest.mark.parametrize("name,b2_text,expected", CORPUS, ids=[c[0] for c in CORPUS])
def test_corpus_round_trip_compiles_via_piece_schema(name, b2_text, expected):
    # The round-trip dict isn't just structurally equal -- it must also be
    # accepted by PieceSchema itself (spec-2.md SS3: the parser's dict feeds
    # straight into PieceSchema(**dict)).
    from leadsheet.schema import PieceSchema

    PieceSchema(**dsl.parse_dsl(b2_text))
