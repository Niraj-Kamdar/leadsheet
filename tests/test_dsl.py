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


def test_melody_raw_line():
    result = dsl.parse_dsl('bpm=100\nmelody "Flute" name="lead" raw: E5[.4;.4], r[.4], C5[.4;.4]\n')
    assert result["tracks"][0]["events"] == [{"type": "raw", "notes": "E5[.4;.4], r[.4], C5[.4;.4]"}]


def test_melody_notes_line():
    result = dsl.parse_dsl('bpm=100\nmelody "Violin" notes: E5@1/4 r@1/8 G5@1/4\n')
    assert result["tracks"][0]["events"] == [
        {"type": "note", "note": "E5", "duration": "1/4"},
        {"type": "note", "rest": True, "duration": "1/8"},
        {"type": "note", "note": "G5", "duration": "1/4"},
    ]


def test_melody_track_can_use_chord_list_segment():
    # Not all melody tracks use raw:/notes: -- genre-recipes.md's Chiptune and
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


def test_error_raw_missing_content():
    with pytest.raises(dsl.DslSyntaxError, match=r"line 2.*requires a note-string"):
        dsl.parse_dsl('bpm=100\nmelody "Violin" raw:\n')


def test_error_notes_token_missing_at_sign():
    with pytest.raises(dsl.DslSyntaxError, match=r"line 2.*E5"):
        dsl.parse_dsl('bpm=100\nmelody "Violin" notes: E5\n')


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
melody "Flute" name="melody" raw: E5[.4;.4], r[.4], C5[.4;.4], D5[.4;.4], E5[.2;.2], r[.4], A4[.4;.4], C5[.4;.4], B4[.2;.2], r[.2], G4[.4;.4], A4[.4;.4], B4[.4;.4], C5[.2;.2], r[.2], A4[.2;.2], G4[.2;.2], E4[.2;.2]
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
                {
                    "type": "raw",
                    "notes": "E5[.4;.4], r[.4], C5[.4;.4], D5[.4;.4], E5[.2;.2], r[.4], A4[.4;.4], "
                    "C5[.4;.4], B4[.2;.2], r[.2], G4[.4;.4], A4[.4;.4], B4[.4;.4], C5[.2;.2], r[.2], "
                    "A4[.2;.2], G4[.2;.2], E4[.2;.2]",
                }
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
melody "Electric Guitar (clean)" name="lead" start=8 raw: E5[1;1], D5[1;1], C5[1;1], D5[1;1]
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
            "events": [{"type": "raw", "notes": "E5[1;1], D5[1;1], C5[1;1], D5[1;1]"}],
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
