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
restricted to `raw:`/`notes:` lines. But the actual repo corpus
(genre-recipes.md's Chiptune and EDM examples) has `role: "melody"` tracks
whose events are ordinary ChordEvents with an arpeggio style -- there is no
grammar-level reason to forbid that, and the round-trip equivalence test
(spec-2.md SS6) requires reproducing those examples exactly. So here the
segment-line mechanism is role-agnostic: any non-drums track may use it,
and `raw:`/`notes:` remain available line-forms on any non-drums track
header too (only melody tracks make musical use of them in practice).
"""

from __future__ import annotations

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
HEADER_MOD_KEYS = {"name", "start", "vol", "repeat"}
SEGMENT_MOD_KEYS = {"subdiv", "oct", "pattern", "vel"}
TOP_LEVEL_KEYS = {"bpm", "title", "key"}

_HEADER_FIELD_NAMES = {"name": "name", "start": "start_bar", "vol": "volume", "repeat": "repeat"}


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
    recover verbatim trailing content (e.g. a `raw:` note-string).
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
    tokens: list[_Token], start: int, terminator_idx: int, line_no: int, *, allow_header_mods: bool
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
                        f"line {line_no}: '{key}=' is only valid on a track header line, not a segment line"
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
        elif bare in ("raw", "notes"):
            if content_kind is not None:
                raise DslSyntaxError(f"line {line_no}: duplicate {bare!r} keyword")
            content_kind = bare
        else:
            raise DslSyntaxError(
                f"line {line_no}: unrecognized token {bare!r} -- expected a style keyword "
                f"({'|'.join(sorted(STYLE_VALUES))}), 'raw', 'notes', or a key=value modifier"
            )
    return header_mods, segment_mods, style, content_kind


def _header_fields(header_mods: dict, line_no: int) -> dict:
    fields: dict = {}
    for key, value in header_mods.items():
        field_name = _HEADER_FIELD_NAMES[key]
        if key == "name":
            fields[field_name] = value
        elif key == "start":
            fields[field_name] = _num(value, line_no, "start=")
        else:  # vol, repeat
            fields[field_name] = int(_num(value, line_no, f"{key}="))
    return fields


def _build_chord_events(style: str | None, segment_mods: dict, content: str, line_no: int) -> list[dict]:
    symbols = content.split()
    if not symbols:
        raise DslSyntaxError(f"line {line_no}: empty chord list")
    events = []
    for symbol in symbols:
        event: dict = {"type": "chord", "chord": symbol, "bars": 1}
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


def _parse_notes_content(content: str, line_no: int) -> list[dict]:
    tokens = content.split()
    if not tokens:
        raise DslSyntaxError(f"line {line_no}: notes: requires at least one <note>@<fraction> token")
    events = []
    for tok in tokens:
        if "@" not in tok:
            raise DslSyntaxError(
                f"line {line_no}: notes token {tok!r} must be <note>@<fraction> or r@<fraction>"
            )
        left, _, right = tok.partition("@")
        if not right:
            raise DslSyntaxError(f"line {line_no}: notes token {tok!r} is missing a fraction after '@'")
        if left == "r":
            events.append({"type": "note", "rest": True, "duration": right})
        elif left:
            events.append({"type": "note", "note": left, "duration": right})
        else:
            raise DslSyntaxError(f"line {line_no}: notes token {tok!r} is missing a note name before '@'")
    return events


def _parse_track_header(tokens: list[_Token], line: str, line_no: int) -> tuple[dict, bool]:
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

    if role == "drums":
        if segment_mods or style or content_kind:
            raise DslSyntaxError(
                f"line {line_no}: drums tracks don't take style/subdiv/oct/pattern/vel/raw/notes modifiers"
            )
        if not content:
            raise DslSyntaxError(f"line {line_no}: drums track is missing a comma-separated drum-token list")
        pattern_tokens = [t.strip() for t in content.split(",")]
        if any(not t for t in pattern_tokens):
            raise DslSyntaxError(f"line {line_no}: empty drum token in list: {content!r}")
        track = {"role": role, "instrument": instrument_value, **fields, "drum_pattern": ", ".join(pattern_tokens)}
        return track, True

    if content_kind == "raw":
        if segment_mods or style:
            raise DslSyntaxError(f"line {line_no}: raw: can't be combined with style/subdiv/oct/pattern/vel")
        if not content:
            raise DslSyntaxError(f"line {line_no}: raw: requires a note-string after it")
        track = {"role": role, "instrument": instrument_value, **fields, "events": [{"type": "raw", "notes": content}]}
        return track, True

    if content_kind == "notes":
        if segment_mods or style:
            raise DslSyntaxError(f"line {line_no}: notes: can't be combined with style/subdiv/oct/pattern/vel")
        if not content:
            raise DslSyntaxError(f"line {line_no}: notes: requires at least one <note>@<fraction> token")
        events = _parse_notes_content(content, line_no)
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


def _parse_segment_line(tokens: list[_Token], line: str, line_no: int) -> list[dict]:
    terminator_idx = _find_terminator(tokens, line_no, "segment line must end with ':' before the chord list")
    _header_mods, segment_mods, style, content_kind = _classify_middle(
        tokens, 0, terminator_idx, line_no, allow_header_mods=False
    )
    if content_kind:
        raise DslSyntaxError(
            f"line {line_no}: '{content_kind}:' is only valid on a track header line, not a segment line"
        )
    content = line[tokens[terminator_idx].end:].strip()
    if not content:
        raise DslSyntaxError(f"line {line_no}: segment line has no chord list after ':'")
    return _build_chord_events(style, segment_mods, content, line_no)


def parse_dsl(text: str) -> dict:
    """Parses B2 text into a `PieceSchema`-shaped kwargs dict. Raises
    `DslSyntaxError` on any structural problem."""
    top_level: dict | None = None
    tracks: list[dict] = []
    current_track: dict | None = None

    for line_no, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        tokens = _tokenize(line, line_no)
        first = tokens[0].text

        if top_level is None:
            top_level = _parse_top_level(tokens, line_no)
            continue

        if first in ROLES:
            if current_track is not None:
                tracks.append(current_track)
                current_track = None
            track, closed = _parse_track_header(tokens, line, line_no)
            if closed:
                tracks.append(track)
            else:
                current_track = track
            continue

        if current_track is None:
            raise DslSyntaxError(
                f"line {line_no}: unrecognized line -- expected a role keyword "
                f"({'|'.join(sorted(ROLES))}) or bpm=, got: {first!r}"
            )
        current_track["events"].extend(_parse_segment_line(tokens, line, line_no))

    if current_track is not None:
        tracks.append(current_track)

    if top_level is None:
        raise DslSyntaxError("line 1: empty input -- expected a top-level line starting with bpm=")

    return {**top_level, "tracks": tracks}
