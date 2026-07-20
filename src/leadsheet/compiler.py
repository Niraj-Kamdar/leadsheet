"""Pure, deterministic compiler: PieceSchema -> musicpy `piece` object.

No model/LLM call happens in here. Every `chord(...)`/`piece(...)` call
this module makes directly explicitly passes `other_messages=[]` -- both
constructors default that kwarg to a shared mutable list in musicpy itself
(confirmed by direct execution: two chords built without passing it share
the same list object), which is a real cross-request state-leak hazard for
a long-lived server process. Never omit it.

Note: `chord.set()` (used by the block/arpeggio_* styles below) builds its
result chord internally without forwarding other_messages at all -- that's
a musicpy-internal limitation this module can't route around, since
`.set()`'s signature doesn't accept the kwarg. It's harmless as long as
nothing ever mutates `.other_messages` in place, which this module never
does.
"""

from __future__ import annotations

from fractions import Fraction

import musicpy as mp

from leadsheet import capabilities
from leadsheet.schema import ChordEvent, NoteEvent, PieceSchema, RawEvent, TrackSchema


def to_float(value: str | int | float) -> float:
    """musicpy's chord.change_interval()/change_duration() only accept
    plain int/float -- passing a Fraction raises TypeError deep inside
    musicpy, so every fraction-string schema field is resolved to a
    float at this boundary, right before it reaches musicpy."""
    if isinstance(value, (int, float)):
        return float(value)
    return float(Fraction(value))


def resolve_instrument(instrument: str | int, *, drums: bool = False) -> int:
    if isinstance(instrument, int):
        return instrument
    table = capabilities.drum_kits() if drums else capabilities.instruments()
    return table[instrument]


def _tile(pattern: list[float], slots: int) -> list[float]:
    return [pattern[i % len(pattern)] for i in range(slots)]


def compile_chord_event(event: ChordEvent) -> "mp.chord":
    bars = to_float(event.bars)
    root_chord = mp.C(event.chord, event.octave)
    override_subdivision = to_float(event.subdivision) if event.subdivision is not None else None
    override_note_duration = to_float(event.note_duration) if event.note_duration is not None else None

    if event.style == "block":
        subdivision = override_subdivision if override_subdivision is not None else 0.0
        return root_chord.set(duration=bars, interval=subdivision, volume=event.velocity)

    if event.style == "root_only":
        return mp.chord(
            [root_chord.notes[0]],
            duration=bars,
            interval=bars,
            volume=event.velocity,
            other_messages=[],
        )

    if event.style == "root_fifth":
        subdivision = override_subdivision if override_subdivision is not None else bars / 2
        root_note = root_chord.notes[0]
        fifth_note = root_chord.notes[2] if len(root_chord) > 2 else root_note.up(7)
        return mp.chord(
            [root_note, fifth_note],
            duration=subdivision,
            interval=subdivision,
            volume=event.velocity,
            other_messages=[],
        )

    if event.style == "walking":
        subdivision = override_subdivision if override_subdivision is not None else bars / 4
        root_note = root_chord.notes[0]
        third_note = root_chord.notes[1] if len(root_chord) > 1 else root_note
        fifth_note = root_chord.notes[2] if len(root_chord) > 2 else root_note
        approach_note = root_note.up(1)
        cycle = [root_note, third_note, fifth_note, approach_note]
        slots = max(1, round(bars / subdivision))
        notes = _tile(cycle, slots)
        return mp.chord(
            notes,
            duration=subdivision,
            interval=subdivision,
            volume=event.velocity,
            other_messages=[],
        )

    # arpeggio_up / arpeggio_updown / custom_pattern all expand via chord.get()
    subdivision = override_subdivision if override_subdivision is not None else 1 / 8
    note_duration = override_note_duration if override_note_duration is not None else 2 * subdivision
    n = len(root_chord)
    if event.style == "custom_pattern":
        pattern = event.pattern
    else:
        slots = max(1, round(bars / subdivision))
        if event.style == "arpeggio_up":
            base_pattern = list(range(1, n + 1))
        else:  # arpeggio_updown -- up then down, no repeated boundary note
            base_pattern = list(range(1, n + 1)) + list(range(n - 1, 1, -1)) if n > 1 else [1]
        pattern = _tile(base_pattern, slots)

    return root_chord.get(pattern).set(duration=note_duration, interval=subdivision, volume=event.velocity)


def compile_note_event(event: NoteEvent) -> "mp.chord":
    if event.rest:
        duration_str = str(Fraction(event.duration).limit_denominator(1024))
        return mp.chord(f"r[{duration_str}]", other_messages=[])
    duration = to_float(event.duration)
    return mp.chord(
        [mp.N(event.note)],
        duration=duration,
        interval=duration,
        volume=event.velocity,
        other_messages=[],
    )


def compile_raw_event(event: RawEvent) -> "mp.chord":
    return mp.chord(event.notes, other_messages=[])


def compile_event(event: ChordEvent | NoteEvent | RawEvent) -> "mp.chord":
    if isinstance(event, ChordEvent):
        return compile_chord_event(event)
    if isinstance(event, NoteEvent):
        return compile_note_event(event)
    return compile_raw_event(event)


def compile_track(track: TrackSchema) -> "mp.chord":
    if track.role == "drums":
        d = mp.drum(pattern=track.drum_pattern, i=resolve_instrument(track.instrument, drums=True))
        base = d.notes
    else:
        fragments = [compile_event(e) for e in track.events]
        base = mp.concat(fragments, mode="|") if len(fragments) > 1 else fragments[0]

    if track.volume is not None:
        base.set_volume(track.volume)

    return base * track.repeat if track.repeat > 1 else base


def assign_channels(tracks: list[TrackSchema]) -> list[int]:
    used = {t.channel for t in tracks if t.channel is not None}
    channels = []
    next_channel = 0
    for track in tracks:
        if track.channel is not None:
            channels.append(track.channel)
            continue
        if track.role == "drums":
            channels.append(9)
            continue
        while next_channel in used or next_channel == 9:
            next_channel += 1
        channels.append(next_channel)
        used.add(next_channel)
        next_channel += 1
    return channels


def compile_piece(schema: PieceSchema) -> "mp.piece":
    compiled_tracks = [compile_track(t) for t in schema.tracks]
    instruments = [
        resolve_instrument(t.instrument, drums=(t.role == "drums")) for t in schema.tracks
    ]
    channels = assign_channels(schema.tracks)
    # mido's track_name meta message requires an actual string -- a bare
    # `None` (an unnamed track) raises deep inside mp.write(), so every
    # track always gets a name, falling back to its role.
    track_names = [t.name if t.name else t.role for t in schema.tracks]
    return mp.piece(
        tracks=compiled_tracks,
        instruments=instruments,
        bpm=schema.bpm,
        start_times=[t.start_bar for t in schema.tracks],
        track_names=track_names,
        channels=channels,
        other_messages=[],
    )
