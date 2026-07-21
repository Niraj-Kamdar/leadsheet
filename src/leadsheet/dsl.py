"""The B2 DSL parser: `.leadsheet` file text -> a `PieceSchema`-shaped dict.

Hand-written line/regex-dispatch parser (spec-2.md Sec.3) -- no tree-sitter,
no grammar-generator. The parser's only job is syntax: recognized line
shape, well-formed key=value modifiers, non-empty chord/token lists. Every
semantic check (chord-symbol validity, instrument/drum-kit lookups,
`custom_pattern`'s pattern-required rule, guardrail limits) is left to
`PieceSchema(**parse_dsl(text))`, same as spec-2.md Sec.3 requires.

Grammar note: spec-2.md's own SS2.2/SS2.5 wording describes the segment-line
mechanism (style + subdiv=/oct=/pattern=/vel= modifiers -> a chord-list) as
if it only applied to chords/bass/custom tracks, with melody tracks
restricted to `notes:` lines. But the actual repo corpus (genre-recipes.md's
Chiptune and EDM examples) has `role: "melody"` tracks whose events are
ordinary ChordEvents with an arpeggio style -- there is no grammar-level
reason to forbid that, and the round-trip equivalence test (spec-2.md SS6)
requires reproducing those examples exactly. So here the segment-line
mechanism is role-agnostic: any non-drums track may use it, and `notes:`
remains an available line-form on any non-drums track header too (only
melody tracks make musical use of it in practice).

Extensions beyond spec-2.md (added after real orchestral-scoring usage
surfaced gaps the original pop/lo-fi/chiptune/riff-rock benchmark corpus
never exercised):
- A chord-list token may carry a `*<bars>` suffix (a plain decimal or
  `<a>/<b>` fraction, e.g. `Am7*0.5`) to override the default 1-bar
  duration -- sub-bar harmonic changes.
- The bare token `r` (optionally with `*<bars>`) in a chord-list is a rest
  -- emits a `NoteEvent(rest=True)` instead of a `ChordEvent`, since `r`
  can never collide with a real chord symbol (chord symbols always start
  with an uppercase note letter).
- `bars=<n>` is a new header modifier mapping to `TrackSchema.
  expected_bars` -- a hard assertion checked by theory_check.py (not here;
  it needs a NoteEvent's real compiled duration, which this pure-syntax
  parser doesn't have access to).
- `define <name>: <content>` / `use: <name> [x<n>] [transpose=<n>]
  [vel=<0-127>]` -- piece-wide named macros. A `define` line is only valid
  between tracks (same scope as a track header) and captures exactly the
  same content shapes a track header can (chord-list segment / `notes:` /
  drum-token-list, the last inferred by the presence of a comma -- chord-
  lists are always space-separated, drum-token-lists always comma-
  separated, so this is unambiguous). `use: <name> [x<n>] [transpose=<n>]
  [vel=<0-127>]` then replays that captured content wherever a chord-list
  segment could go -- inline on a track header, as one of several segment
  lines, or as a drum track's token list -- kind-checked against where it's
  used, with `transpose=`/`vel=` applied to the expanded copy (not valid on
  a drum-kind macro). No nested macros (a macro body can't itself `use:`
  another one).
- `section <name>: <track-fragment line>...` / `use section <name>
  start=<bar>` -- a named group of single-line track-fragments, re-
  triggerable as a unit at a new bar offset (spec-3.md SS4). Each fragment
  line is a complete, self-contained track header (multi-segment tracks
  aren't supported inside a `section` block). `use section` duplicates
  every fragment into the piece's `tracks` list, each fragment's own
  `start=` (default 0) offset by the given `start=`.

V3 melody grammar (spec-3.md SS1): `notes:` replaces the old `raw:`/
`notes:` split entirely -- `raw:` (musicpy's own note-string mini-language)
is removed, and `notes:` is generalized into B2's own native melody
grammar, usable both as a track-header's single inline segment and as an
ordinary segment line. `dur=`/`int=`/`vel=` are segment-level defaults;
each token is a bare note (`E5`), a duration override (`E5@1/4`), a rest
(`r`/`r@1/8`), a simultaneous-note stack (`C5+E5+G5@1/2`), or a repeat-count
suffix on the immediately preceding token (`E5 x8`).
"""

from __future__ import annotations

import re
from fractions import Fraction

# Mirrors schema.py's closed-vocabulary Literal values -- deliberately
# hardcoded here rather than imported, since the parser only needs to
# recognize these tokens structurally (capabilities.py's instrument/chord/
# drum-kit lookups stay exclusively in PieceSchema's validators).
ROLES = {"chords", "bass", "melody", "drums", "custom"}
STYLE_VALUES = {
    "block",
    "arpeggio_up",
    "arpeggio_updown",
    "custom_pattern",
    "root_only",
    "root_fifth",
    "walking",
}
HEADER_MOD_KEYS = {"name", "start", "vol", "repeat", "bars"}
CHORD_SEGMENT_MOD_KEYS = {"subdiv", "oct", "pattern", "vel"}
NOTES_SEGMENT_MOD_KEYS = {"dur", "int", "vel"}
SEGMENT_MOD_KEYS = CHORD_SEGMENT_MOD_KEYS | NOTES_SEGMENT_MOD_KEYS
TOP_LEVEL_KEYS = {"bpm", "title", "key"}

_HEADER_FIELD_NAMES = {
    "name": "name",
    "start": "start_bar",
    "vol": "volume",
    "repeat": "repeat",
    "bars": "expected_bars",
}
_MACRO_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_REPEAT_TOKEN_RE = re.compile(r"^x(\d+)$")

# A small, self-contained pitch-arithmetic helper (letter+accidental+octave
# <-> semitone number) for `use: <name> transpose=<n>` (spec-3.md SS3) --
# independent of musicpy, deliberately not reusing its object model.
_PITCH_CLASS = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
_SHARP_SPELLING = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
_NOTE_RE = re.compile(r"^([A-Ga-g])([#b]*)(-?\d+)$")
_CHORD_ROOT_RE = re.compile(r"^([A-Ga-g])([#b]*)(.*)$")


class DslSyntaxError(Exception):
    """A structural problem in B2 text -- unrecognized line shape,
    malformed key=value modifier, empty chord/token list, etc."""


class _Token:
    __slots__ = ("text", "start", "end")

    def __init__(self, text: str, start: int, end: int):
        self.text = text
        self.start = start
        self.end = end


def _tokenize(line: str, line_no: int) -> list[_Token]:
    """Whitespace-separated tokens, quote-aware (`"..."` may contain
    spaces/parens and is stripped of its quote marks but keeps any
    character -- e.g. a trailing `:` -- immediately following the closing
    quote as part of the same token). Offsets index into `line` itself, so
    callers can slice the ORIGINAL text (not the quote-stripped token) to
    recover verbatim trailing content (e.g. a chord-list/notes-list tail).
    """
    tokens: list[_Token] = []
    i, n = 0, len(line)
    while i < n:
        while i < n and line[i].isspace():
            i += 1
        if i >= n:
            break
        start = i
        buf: list[str] = []
        while i < n and not line[i].isspace():
            if line[i] == '"':
                end_quote = line.find('"', i + 1)
                if end_quote == -1:
                    raise DslSyntaxError(f"line {line_no}: unterminated quoted string")
                buf.append(line[i + 1:end_quote])
                i = end_quote + 1
            else:
                buf.append(line[i])
                i += 1
        tokens.append(_Token("".join(buf), start, i))
    return tokens


def _num(text: str, line_no: int, what: str):
    try:
        return int(text)
    except ValueError:
        pass
    try:
        return float(text)
    except ValueError:
        raise DslSyntaxError(f"line {line_no}: {what} {text!r} is not a number") from None


def _split_kv(text: str, line_no: int) -> tuple[str, str]:
    if "=" not in text:
        raise DslSyntaxError(f"line {line_no}: expected key=value, got: {text!r}")
    key, _, value = text.partition("=")
    if not key or not value:
        raise DslSyntaxError(f"line {line_no}: malformed key=value token: {text!r}")
    return key, value


def _parse_pattern(value: str, line_no: int) -> list:
    if not (value.startswith("[") and value.endswith("]")):
        raise DslSyntaxError(f"line {line_no}: pattern= must be a bracketed list like [1,2,3], got: {value!r}")
    inner = value[1:-1].strip()
    if not inner:
        raise DslSyntaxError(f"line {line_no}: pattern= list is empty")
    return [_num(item.strip(), line_no, "pattern index") for item in inner.split(",")]


def _pitch_class(letter: str, accidentals: str) -> int:
    return (_PITCH_CLASS[letter.upper()] + accidentals.count("#") - accidentals.count("b")) % 12


def _transpose_note_string(note_str: str, semitones: int, line_no: int) -> str:
    m = _NOTE_RE.match(note_str)
    if not m:
        raise DslSyntaxError(f"line {line_no}: {note_str!r} isn't a transposable note (expected e.g. 'E5', 'C#4')")
    letter, accidentals, octave = m.groups()
    absolute = (int(octave) + 1) * 12 + _pitch_class(letter, accidentals) + semitones
    new_octave = absolute // 12 - 1
    return f"{_SHARP_SPELLING[absolute % 12]}{new_octave}"


def _transpose_chord_symbol(chord: str, octave: int, semitones: int, line_no: int) -> tuple[str, int]:
    m = _CHORD_ROOT_RE.match(chord)
    if not m:
        raise DslSyntaxError(f"line {line_no}: {chord!r} isn't a transposable chord symbol")
    letter, accidentals, suffix = m.groups()
    shifted = _pitch_class(letter, accidentals) + semitones
    new_octave = octave + shifted // 12
    return _SHARP_SPELLING[shifted % 12] + suffix, new_octave


def _transpose_event(event: dict, semitones: int, line_no: int) -> dict:
    event = dict(event)
    if event["type"] == "chord":
        event["chord"], event["octave"] = _transpose_chord_symbol(
            event["chord"], event.get("octave", 3), semitones, line_no
        )
    elif event["type"] == "note" and not event.get("rest"):
        if "note" in event:
            event["note"] = _transpose_note_string(event["note"], semitones, line_no)
        else:
            event["notes"] = [_transpose_note_string(p, semitones, line_no) for p in event["notes"]]
    return event


def _parse_top_level(tokens: list[_Token], line_no: int) -> dict:
    result: dict = {}
    for tok in tokens:
        key, value = _split_kv(tok.text, line_no)
        if key not in TOP_LEVEL_KEYS:
            raise DslSyntaxError(
                f"line {line_no}: unrecognized top-level key {key!r} -- expected one of bpm=/title=/key="
            )
        if key in result:
            raise DslSyntaxError(f"line {line_no}: duplicate {key}= on the top-level line")
        result[key] = value
    if "bpm" not in result:
        raise DslSyntaxError(f"line {line_no}: top-level line must set bpm=<number>")
    result["bpm"] = _num(result["bpm"], line_no, "bpm")
    return result


def _find_terminator(tokens: list[_Token], line_no: int, what: str) -> int:
    for idx, tok in enumerate(tokens):
        if tok.text.endswith(":"):
            return idx
    raise DslSyntaxError(f"line {line_no}: {what} -- no ':' found")


def _classify_middle(
    tokens: list[_Token],
    start: int,
    terminator_idx: int,
    line_no: int,
    *,
    allow_header_mods: bool,
    context: str = "segment line",
) -> tuple[dict, dict, str | None, str | None]:
    """Classifies tokens[start:terminator_idx+1] (colon stripped from the
    terminator token) into (header_mods, segment_mods, style, content_kind).
    """
    header_mods: dict[str, str] = {}
    segment_mods: dict[str, str] = {}
    style: str | None = None
    content_kind: str | None = None

    for idx in range(start, terminator_idx + 1):
        tok = tokens[idx]
        bare = tok.text[:-1] if idx == terminator_idx else tok.text
        if not bare:
            continue
        if "=" in bare:
            key, value = _split_kv(bare, line_no)
            if key in HEADER_MOD_KEYS:
                if not allow_header_mods:
                    raise DslSyntaxError(
                        f"line {line_no}: '{key}=' is only valid on a track header line, not a {context}"
                    )
                if key in header_mods:
                    raise DslSyntaxError(f"line {line_no}: duplicate {key}= modifier")
                header_mods[key] = value
            elif key in SEGMENT_MOD_KEYS:
                if key in segment_mods:
                    raise DslSyntaxError(f"line {line_no}: duplicate {key}= modifier")
                segment_mods[key] = value
            else:
                raise DslSyntaxError(f"line {line_no}: unrecognized modifier key {key!r} in {bare!r}")
        elif bare in STYLE_VALUES:
            if style is not None:
                raise DslSyntaxError(f"line {line_no}: duplicate style token {bare!r}")
            style = bare
        elif bare in ("notes", "use"):
            if content_kind is not None:
                raise DslSyntaxError(f"line {line_no}: duplicate {bare!r} keyword")
            content_kind = bare
        else:
            raise DslSyntaxError(
                f"line {line_no}: unrecognized token {bare!r} -- expected a style keyword "
                f"({'|'.join(sorted(STYLE_VALUES))}), 'notes', 'use', or a key=value modifier"
            )
    return header_mods, segment_mods, style, content_kind


def _header_fields(header_mods: dict, line_no: int) -> dict:
    fields: dict = {}
    for key, value in header_mods.items():
        field_name = _HEADER_FIELD_NAMES[key]
        if key == "name":
            fields[field_name] = value
        elif key in ("start", "bars"):
            fields[field_name] = _num(value, line_no, f"{key}=")
        else:  # vol, repeat
            fields[field_name] = int(_num(value, line_no, f"{key}="))
    return fields


def _eval_bars(text: str, line_no: int) -> float:
    """Evaluates a chord-list token's `*<bars>` suffix -- a plain decimal
    ("0.5", "2") or an "<a>/<b>" fraction ("1/2"), same string shapes
    `fractions.Fraction` itself accepts (mirrors schema.py's parse_fraction
    convention). Unlike subdiv=/vel=/etc, this is evaluated eagerly to a
    real number here: ChordEvent.bars/NoteEvent.duration in this position
    need a number, not a passthrough fraction string."""
    try:
        return float(Fraction(text))
    except (ValueError, ZeroDivisionError):
        raise DslSyntaxError(f"line {line_no}: bars value {text!r} is not a number") from None


def _build_chord_events(style: str | None, segment_mods: dict, content: str, line_no: int) -> list[dict]:
    invalid = set(segment_mods) & {"dur", "int"}
    if invalid:
        raise DslSyntaxError(
            f"line {line_no}: {'/'.join(sorted(k + '=' for k in invalid))} isn't valid on a chord-list "
            "segment (only subdiv=/oct=/pattern=/vel=)"
        )
    tokens = content.split()
    if not tokens:
        raise DslSyntaxError(f"line {line_no}: empty chord list")
    events = []
    for token in tokens:
        if "*" in token:
            symbol, _, bars_suffix = token.rpartition("*")
            if not symbol:
                raise DslSyntaxError(f"line {line_no}: {token!r} is missing a chord/rest before '*'")
            bars: float | int = _eval_bars(bars_suffix, line_no)
        else:
            symbol, bars = token, 1

        if symbol == "r":
            events.append({"type": "note", "rest": True, "duration": bars})
            continue

        event: dict = {"type": "chord", "chord": symbol, "bars": bars}
        if style is not None:
            event["style"] = style
        if "oct" in segment_mods:
            event["octave"] = int(_num(segment_mods["oct"], line_no, "oct="))
        if "subdiv" in segment_mods:
            event["subdivision"] = segment_mods["subdiv"]
        if "vel" in segment_mods:
            event["velocity"] = int(_num(segment_mods["vel"], line_no, "vel="))
        if "pattern" in segment_mods:
            event["pattern"] = _parse_pattern(segment_mods["pattern"], line_no)
        events.append(event)
    return events


def _validate_notes_segment_mods(style: str | None, segment_mods: dict, line_no: int) -> None:
    if style is not None:
        raise DslSyntaxError(f"line {line_no}: notes: can't be combined with a style keyword")
    invalid = set(segment_mods) - NOTES_SEGMENT_MOD_KEYS
    if invalid:
        raise DslSyntaxError(
            f"line {line_no}: {'/'.join(sorted(k + '=' for k in invalid))} isn't valid on a notes: "
            "segment (only dur=/int=/vel=)"
        )


def _parse_one_note_token(tok: str, seg_dur: str | None, seg_int: str | None, seg_vel: str | None, line_no: int) -> dict:
    if "@" in tok:
        left, _, override = tok.partition("@")
        if not override:
            raise DslSyntaxError(f"line {line_no}: notes token {tok!r} is missing a fraction after '@'")
        duration: str = override
        interval: str | None = None
    else:
        left = tok
        if seg_dur is None:
            raise DslSyntaxError(
                f"line {line_no}: note token {tok!r} has no '@<fraction>' duration override and no "
                "segment dur=<fraction> default"
            )
        duration = seg_dur
        interval = seg_int

    if not left:
        raise DslSyntaxError(f"line {line_no}: notes token {tok!r} is missing a note/rest before '@'")

    if left == "r":
        event: dict = {"type": "note", "rest": True, "duration": duration}
    elif "+" in left:
        pitches = left.split("+")
        if any(not p for p in pitches):
            raise DslSyntaxError(f"line {line_no}: malformed note stack {tok!r}")
        event = {"type": "note", "notes": pitches, "duration": duration}
        if interval is not None:
            event["interval"] = interval
    else:
        event = {"type": "note", "note": left, "duration": duration}
        if interval is not None:
            event["interval"] = interval

    if seg_vel is not None:
        event["velocity"] = int(_num(seg_vel, line_no, "vel="))
    return event


def _parse_notes_tokens(content: str, segment_mods: dict, line_no: int) -> list[dict]:
    tokens = content.split()
    if not tokens:
        raise DslSyntaxError(f"line {line_no}: notes: requires at least one note/rest/stack token")
    seg_dur = segment_mods.get("dur")
    seg_int = segment_mods.get("int")
    seg_vel = segment_mods.get("vel")
    events: list[dict] = []
    for tok in tokens:
        repeat_match = _REPEAT_TOKEN_RE.match(tok)
        if repeat_match:
            count = int(repeat_match.group(1))
            if count < 1:
                raise DslSyntaxError(f"line {line_no}: repeat count must be >= 1, got: {tok!r}")
            if not events:
                raise DslSyntaxError(f"line {line_no}: {tok!r} has no preceding note/rest/stack token to repeat")
            last = events[-1]
            events.extend(dict(last) for _ in range(count - 1))
            continue
        events.append(_parse_one_note_token(tok, seg_dur, seg_int, seg_vel, line_no))
    return events


def _parse_use_content(content: str, line_no: int) -> tuple[str, int, int | None, int | None]:
    parts = content.split()
    if not parts:
        raise DslSyntaxError(f"line {line_no}: use: requires a macro name")
    name = parts[0]
    count = 1
    transpose: int | None = None
    vel: int | None = None
    seen: set[str] = set()
    for part in parts[1:]:
        repeat_match = _REPEAT_TOKEN_RE.match(part)
        if repeat_match:
            if "x" in seen:
                raise DslSyntaxError(f"line {line_no}: duplicate x<n> on use:")
            seen.add("x")
            count = int(repeat_match.group(1))
            if count < 1:
                raise DslSyntaxError(f"line {line_no}: use: repeat count must be >= 1, got: {part!r}")
            continue
        if "=" in part:
            key, value = _split_kv(part, line_no)
            if key not in ("transpose", "vel"):
                raise DslSyntaxError(f"line {line_no}: use: only takes x<n>/transpose=/vel=, got: {part!r}")
            if key in seen:
                raise DslSyntaxError(f"line {line_no}: duplicate {key}= on use:")
            seen.add(key)
            if key == "transpose":
                transpose = int(_num(value, line_no, "transpose="))
            else:
                vel = int(_num(value, line_no, "vel="))
            continue
        raise DslSyntaxError(
            f"line {line_no}: use: only takes x<n>/transpose=/vel= after the macro name, got: {part!r}"
        )
    return name, count, transpose, vel


def _expand_use(
    macros: dict, name: str, count: int, transpose: int | None, vel: int | None, line_no: int, *, expected_kind: str
):
    if name not in macros:
        raise DslSyntaxError(f"line {line_no}: undefined macro {name!r} -- no matching 'define {name}:' line")
    kind, payload = macros[name]
    if kind != expected_kind:
        raise DslSyntaxError(
            f"line {line_no}: macro {name!r} is a {kind!r}-kind macro, but this position needs a "
            f"{expected_kind!r}-kind macro"
        )
    if kind == "drum":
        if transpose is not None or vel is not None:
            raise DslSyntaxError(f"line {line_no}: transpose=/vel= aren't valid on a drum-pattern use:")
        tokens = [t.strip() for t in payload.split(",")]
        return ", ".join(tokens * count)
    events = [dict(event) for _ in range(count) for event in payload]
    if transpose is not None:
        events = [_transpose_event(e, transpose, line_no) for e in events]
    if vel is not None:
        for e in events:
            e["velocity"] = vel
    return events


def _parse_define(tokens: list[_Token], line: str, line_no: int, macros: dict) -> None:
    if len(tokens) < 2:
        raise DslSyntaxError(f"line {line_no}: define is missing a macro name")

    name_bare = tokens[1].text[:-1] if tokens[1].text.endswith(":") else tokens[1].text
    if not _MACRO_NAME_RE.match(name_bare):
        raise DslSyntaxError(
            f"line {line_no}: {name_bare!r} is not a valid macro name "
            "(letters/digits/underscore, must start with a letter or underscore)"
        )
    if name_bare in macros:
        raise DslSyntaxError(f"line {line_no}: macro {name_bare!r} is already defined")

    terminator_idx = _find_terminator(tokens[1:], line_no, "define line must end with ':' somewhere") + 1
    _header_mods, segment_mods, style, content_kind = _classify_middle(
        tokens, 2, terminator_idx, line_no, allow_header_mods=False, context="define body"
    )
    content = line[tokens[terminator_idx].end:].strip()

    if content_kind == "use":
        raise DslSyntaxError(f"line {line_no}: a macro body can't itself use: another macro (no nested macros)")

    if content_kind == "notes":
        _validate_notes_segment_mods(style, segment_mods, line_no)
        if not content:
            raise DslSyntaxError(f"line {line_no}: notes: requires at least one note/rest/stack token")
        macros[name_bare] = ("events", _parse_notes_tokens(content, segment_mods, line_no))
        return

    if not content:
        raise DslSyntaxError(f"line {line_no}: define {name_bare!r} has no content after ':'")

    if content.startswith(("notes:", "use:")):
        # The most likely cause: a colon was written right after the macro
        # name (`define name: notes: ...`) instead of before notes:/use:
        # (`define name notes: ...`) -- that misplaced colon becomes the
        # terminator, so notes:/use: never gets classified and falls
        # through to here as literal text instead. Give a specific nudge
        # rather than silently (and wrongly) treating it as a drum pattern.
        keyword = content.split(":", 1)[0]
        raise DslSyntaxError(
            f"line {line_no}: content starts with '{keyword}:' but the ':' right after the macro "
            f"name already ended the header -- write 'define {name_bare} {keyword}: ...' "
            f"(no ':' after the name), not 'define {name_bare}: {keyword}: ...'"
        )

    if "," in content:
        # Drum-token-lists are always comma-separated and chord-lists never
        # are (they're space-separated) -- an unambiguous kind signal.
        if segment_mods or style:
            raise DslSyntaxError(f"line {line_no}: a drum-token-list macro doesn't take style/subdiv/oct/pattern/vel")
        pattern_tokens = [t.strip() for t in content.split(",")]
        if any(not t for t in pattern_tokens):
            raise DslSyntaxError(f"line {line_no}: empty drum token in list: {content!r}")
        macros[name_bare] = ("drum", ", ".join(pattern_tokens))
        return

    macros[name_bare] = ("events", _build_chord_events(style, segment_mods, content, line_no))


def _parse_track_header(
    tokens: list[_Token], line: str, line_no: int, macros: dict
) -> tuple[dict, bool]:
    """Returns (track_dict, closed). `closed=False` means the track stays
    open for following segment lines."""
    role = tokens[0].text
    if len(tokens) < 2:
        raise DslSyntaxError(f"line {line_no}: track header is missing an instrument")

    terminator_idx = _find_terminator(
        tokens[1:], line_no, "track header line must end with ':' somewhere"
    ) + 1

    instrument_bare = tokens[1].text[:-1] if terminator_idx == 1 else tokens[1].text
    instrument_value: str | int = int(instrument_bare) if instrument_bare.isdigit() else instrument_bare

    header_mods, segment_mods, style, content_kind = _classify_middle(
        tokens, 2, terminator_idx, line_no, allow_header_mods=True
    )
    fields = _header_fields(header_mods, line_no)
    content = line[tokens[terminator_idx].end:].strip()

    if "bars" in header_mods and role == "drums":
        raise DslSyntaxError(
            f"line {line_no}: bars= isn't checkable on a drums track (it has no events to sum)"
        )

    if role == "drums":
        if segment_mods or style:
            raise DslSyntaxError(f"line {line_no}: drums tracks don't take style/subdiv/oct/pattern/vel modifiers")
        if content_kind == "notes":
            raise DslSyntaxError(f"line {line_no}: drums tracks don't take {content_kind}:")
        if content_kind == "use":
            if not content:
                raise DslSyntaxError(f"line {line_no}: use: requires a macro name")
            name, count, transpose, vel = _parse_use_content(content, line_no)
            drum_pattern = _expand_use(macros, name, count, transpose, vel, line_no, expected_kind="drum")
            track = {"role": role, "instrument": instrument_value, **fields, "drum_pattern": drum_pattern}
            return track, True
        if not content:
            raise DslSyntaxError(f"line {line_no}: drums track is missing a comma-separated drum-token list")
        pattern_tokens = [t.strip() for t in content.split(",")]
        if any(not t for t in pattern_tokens):
            raise DslSyntaxError(f"line {line_no}: empty drum token in list: {content!r}")
        track = {"role": role, "instrument": instrument_value, **fields, "drum_pattern": ", ".join(pattern_tokens)}
        return track, True

    if content_kind == "notes":
        _validate_notes_segment_mods(style, segment_mods, line_no)
        if not content:
            raise DslSyntaxError(f"line {line_no}: notes: requires at least one note/rest/stack token")
        events = _parse_notes_tokens(content, segment_mods, line_no)
        track = {"role": role, "instrument": instrument_value, **fields, "events": events}
        return track, True

    if content_kind == "use":
        if segment_mods or style:
            raise DslSyntaxError(f"line {line_no}: use: can't be combined with style/subdiv/oct/pattern/vel")
        if not content:
            raise DslSyntaxError(f"line {line_no}: use: requires a macro name")
        name, count, transpose, vel = _parse_use_content(content, line_no)
        events = _expand_use(macros, name, count, transpose, vel, line_no, expected_kind="events")
        track = {"role": role, "instrument": instrument_value, **fields, "events": events}
        return track, True

    if not content:
        if segment_mods or style:
            raise DslSyntaxError(
                f"line {line_no}: style/modifiers with no chord list -- end the header with a bare ':' "
                "to open a multi-segment track, or add a chord list after ':'"
            )
        track = {"role": role, "instrument": instrument_value, **fields, "events": []}
        return track, False

    events = _build_chord_events(style, segment_mods, content, line_no)
    track = {"role": role, "instrument": instrument_value, **fields, "events": events}
    return track, True


def _parse_segment_line(tokens: list[_Token], line: str, line_no: int, macros: dict) -> list[dict]:
    terminator_idx = _find_terminator(tokens, line_no, "segment line must end with ':' before the chord list")
    _header_mods, segment_mods, style, content_kind = _classify_middle(
        tokens, 0, terminator_idx, line_no, allow_header_mods=False
    )
    content = line[tokens[terminator_idx].end:].strip()

    if content_kind == "use":
        if segment_mods or style:
            raise DslSyntaxError(f"line {line_no}: use: can't be combined with style/subdiv/oct/pattern/vel")
        if not content:
            raise DslSyntaxError(f"line {line_no}: use: requires a macro name")
        name, count, transpose, vel = _parse_use_content(content, line_no)
        return _expand_use(macros, name, count, transpose, vel, line_no, expected_kind="events")

    if content_kind == "notes":
        _validate_notes_segment_mods(style, segment_mods, line_no)
        if not content:
            raise DslSyntaxError(f"line {line_no}: notes: requires at least one note/rest/stack token")
        return _parse_notes_tokens(content, segment_mods, line_no)

    if content_kind:
        raise DslSyntaxError(
            f"line {line_no}: '{content_kind}:' is only valid on a track header line, not a segment line"
        )
    if not content:
        raise DslSyntaxError(f"line {line_no}: segment line has no chord list after ':'")
    return _build_chord_events(style, segment_mods, content, line_no)


def _parse_section_header(tokens: list[_Token], line_no: int) -> str:
    if len(tokens) != 2 or not tokens[1].text.endswith(":"):
        raise DslSyntaxError(
            f"line {line_no}: section header line must look like 'section <name>:' with nothing "
            "after the colon -- fragments go on their own lines below"
        )
    name_bare = tokens[1].text[:-1]
    if not _MACRO_NAME_RE.match(name_bare):
        raise DslSyntaxError(
            f"line {line_no}: {name_bare!r} is not a valid section name "
            "(letters/digits/underscore, must start with a letter or underscore)"
        )
    return name_bare


def _parse_use_section(tokens: list[_Token], line_no: int, sections: dict) -> list[dict]:
    if len(tokens) < 3 or tokens[1].text != "section":
        raise DslSyntaxError(f"line {line_no}: expected 'use section <name> start=<bar>'")
    name = tokens[2].text
    if name not in sections:
        raise DslSyntaxError(f"line {line_no}: undefined section {name!r} -- no matching 'section {name}:' block")
    start_value = None
    for tok in tokens[3:]:
        key, value = _split_kv(tok.text, line_no)
        if key != "start":
            raise DslSyntaxError(f"line {line_no}: 'use section' only takes start=<bar>, got: {key}=")
        if start_value is not None:
            raise DslSyntaxError(f"line {line_no}: duplicate start= on 'use section'")
        start_value = _num(value, line_no, "start=")
    if start_value is None:
        raise DslSyntaxError(f"line {line_no}: 'use section {name}' requires start=<bar>")
    result = []
    for fragment in sections[name]:
        copy = {**fragment, "start_bar": fragment.get("start_bar", 0) + start_value}
        if "events" in copy:
            copy["events"] = [dict(e) for e in copy["events"]]
        result.append(copy)
    return result


def parse_dsl(text: str) -> dict:
    """Parses B2 text into a `PieceSchema`-shaped kwargs dict. Raises
    `DslSyntaxError` on any structural problem."""
    lines = text.splitlines()
    n = len(lines)
    top_level: dict | None = None
    tracks: list[dict] = []
    current_track: dict | None = None
    macros: dict[str, tuple[str, object]] = {}
    sections: dict[str, list[dict]] = {}

    idx = 0
    while idx < n:
        line = lines[idx]
        line_no = idx + 1
        if not line.strip():
            idx += 1
            continue
        tokens = _tokenize(line, line_no)
        first = tokens[0].text

        if top_level is None:
            top_level = _parse_top_level(tokens, line_no)
            idx += 1
            continue

        if first == "define":
            if current_track is not None:
                raise DslSyntaxError(
                    f"line {line_no}: 'define' can't appear inside an open track -- "
                    "close the current track first (a define line only makes sense between tracks)"
                )
            _parse_define(tokens, line, line_no, macros)
            idx += 1
            continue

        if first == "section":
            if current_track is not None:
                raise DslSyntaxError(
                    f"line {line_no}: 'section' can't appear inside an open track -- "
                    "close the current track first"
                )
            name = _parse_section_header(tokens, line_no)
            if name in sections:
                raise DslSyntaxError(f"line {line_no}: section {name!r} is already defined")
            fragments: list[dict] = []
            idx += 1
            while idx < n:
                frag_line = lines[idx]
                frag_line_no = idx + 1
                if not frag_line.strip():
                    break
                frag_tokens = _tokenize(frag_line, frag_line_no)
                if frag_tokens[0].text not in ROLES:
                    break
                frag_track, closed = _parse_track_header(frag_tokens, frag_line, frag_line_no, macros)
                if not closed:
                    raise DslSyntaxError(
                        f"line {frag_line_no}: multi-segment tracks aren't supported inside 'section' "
                        "blocks -- write this fragment as one self-contained line"
                    )
                fragments.append(frag_track)
                idx += 1
            if not fragments:
                raise DslSyntaxError(f"line {line_no}: section {name!r} has no track fragments")
            sections[name] = fragments
            continue

        if first == "use" and len(tokens) > 1 and tokens[1].text == "section":
            if current_track is not None:
                raise DslSyntaxError(
                    f"line {line_no}: 'use section' can't appear inside an open track -- "
                    "close the current track first"
                )
            tracks.extend(_parse_use_section(tokens, line_no, sections))
            idx += 1
            continue

        if first in ROLES:
            if current_track is not None:
                tracks.append(current_track)
                current_track = None
            track, closed = _parse_track_header(tokens, line, line_no, macros)
            if closed:
                tracks.append(track)
            else:
                current_track = track
            idx += 1
            continue

        if current_track is None:
            raise DslSyntaxError(
                f"line {line_no}: unrecognized line -- expected a role keyword "
                f"({'|'.join(sorted(ROLES))}), 'define', 'section', 'use section', or bpm=, got: {first!r}"
            )
        current_track["events"].extend(_parse_segment_line(tokens, line, line_no, macros))
        idx += 1

    if current_track is not None:
        tracks.append(current_track)

    if top_level is None:
        raise DslSyntaxError("line 1: empty input -- expected a top-level line starting with bpm=")

    return {**top_level, "tracks": tracks}
