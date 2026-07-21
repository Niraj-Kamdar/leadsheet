"""The Intent Schema: the contract between the Skill and the server.

Deliberately not musicpy's internal to_dict()/write_json() shape. Built
around chord symbols ("Am7", "G7sus4") since that notation already has
huge presence in an LLM's training data -- the model should never have to
think about musicpy's @/%/^ operators at all.
"""

from __future__ import annotations

from fractions import Fraction
from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field, field_validator, model_validator

from leadsheet import capabilities, limits

FractionLike = Union[str, float, int]


def parse_fraction(value: FractionLike, field_name: str) -> Fraction:
    try:
        if isinstance(value, str):
            return Fraction(value)
        return Fraction(value).limit_denominator(1024)
    except (ValueError, ZeroDivisionError) as exc:
        raise ValueError(
            f"{field_name}={value!r} is not a valid fraction (e.g. \"1/8\" or 0.25)"
        ) from exc


class ChordEvent(BaseModel):
    type: Literal["chord"]
    chord: str
    octave: int = 3
    bars: float = Field(gt=0)
    style: Literal[
        "block",
        "arpeggio_up",
        "arpeggio_updown",
        "custom_pattern",
        "root_only",
        "root_fifth",
        "walking",
    ] = "block"
    pattern: list[float] | None = None
    subdivision: FractionLike | None = None
    note_duration: FractionLike | None = None
    velocity: int = Field(default=100, ge=0, le=127)

    @field_validator("chord")
    @classmethod
    def _validate_chord(cls, v: str) -> str:
        if not capabilities.is_valid_chord_symbol(v):
            suggestion = capabilities.suggest_chord(v)
            hint = f" Did you mean: {suggestion}?" if suggestion else ""
            raise ValueError(f"'{v}' is not a valid chord symbol.{hint}")
        return v

    @field_validator("subdivision", "note_duration")
    @classmethod
    def _validate_fraction_fields(cls, v, info):
        if v is None:
            return v
        parse_fraction(v, info.field_name)
        return v

    @model_validator(mode="after")
    def _validate_pattern(self) -> "ChordEvent":
        if self.style == "custom_pattern":
            if not self.pattern:
                raise ValueError(
                    "pattern is required and must be non-empty when style == 'custom_pattern'"
                )
        elif self.pattern is not None:
            raise ValueError(
                f"pattern is only valid when style == 'custom_pattern' (got style={self.style!r})"
            )
        return self


class NoteEvent(BaseModel):
    type: Literal["note"]
    note: str | None = None
    notes: list[str] | None = None
    duration: FractionLike
    interval: FractionLike | None = None
    rest: bool = False
    velocity: int = Field(default=100, ge=0, le=127)

    @field_validator("duration", "interval")
    @classmethod
    def _validate_duration_fields(cls, v, info):
        if v is None:
            return v
        parse_fraction(v, info.field_name)
        return v

    @model_validator(mode="after")
    def _validate_note_or_rest(self) -> "NoteEvent":
        set_count = int(self.rest) + int(self.note is not None) + int(self.notes is not None)
        if set_count != 1:
            raise ValueError("exactly one of rest, note, notes must be set")
        return self


Event = Annotated[Union[ChordEvent, NoteEvent], Field(discriminator="type")]


def _structural_bar_sum(events: list[Event] | None) -> float:
    """Sum of ChordEvent.bars/NoteEvent.duration across `events` -- the
    cheap structural guardrail sum. theory_check.compute_track_lengths does
    the fuller computation for reporting/assertions."""
    if not events:
        return 0.0
    return float(sum(
        e.bars if isinstance(e, ChordEvent) else parse_fraction(e.duration, "duration")
        for e in events
    ))


class TrackSchema(BaseModel):
    name: str | None = None
    role: Literal["chords", "bass", "melody", "drums", "custom"]
    instrument: str | int
    channel: int | None = Field(default=None, ge=0, le=15)
    start_bar: float = Field(default=0, ge=0)
    volume: int | None = Field(default=None, ge=0, le=127)
    repeat: int = Field(default=1, ge=1)
    events: list[Event] | None = None
    drum_pattern: str | None = None
    # Optional author-declared "this track's events should sum to exactly
    # N bars" assertion. Not checked here (a RawEvent's real duration can
    # only be known by actually parsing its note-string with musicpy,
    # which schema.py can't do without a circular import on compiler.py) --
    # theory_check.validate() checks it and reports a mismatch as an error.
    expected_bars: float | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def _validate_instrument(self) -> "TrackSchema":
        v = self.instrument
        if self.role == "drums":
            valid_ints = capabilities.drum_kits().values()
            if isinstance(v, int):
                if v not in valid_ints:
                    raise ValueError(
                        f"drum instrument {v} is not a known drum-kit program number "
                        "(call list_capabilities for the full list)"
                    )
            elif v not in capabilities.drum_kits():
                raise ValueError(
                    f"'{v}' is not a known drum-kit name (call list_capabilities for the full list)"
                )
        else:
            if isinstance(v, int):
                if not 1 <= v <= 128:
                    raise ValueError(f"instrument int {v} must be in 1..128")
            elif v not in capabilities.instruments():
                raise ValueError(
                    f"'{v}' is not a known General MIDI instrument name (call list_capabilities for the full list)"
                )
        return self

    @model_validator(mode="after")
    def _validate_channel_and_role_payload(self) -> "TrackSchema":
        if self.channel == 9 and self.role != "drums":
            raise ValueError("channel 9 is reserved for drum tracks")
        if self.role == "drums":
            if not self.drum_pattern:
                raise ValueError("drum_pattern is required when role == 'drums'")
            if self.events:
                raise ValueError("events must be absent when role == 'drums'")
        else:
            if self.drum_pattern:
                raise ValueError("drum_pattern is only valid when role == 'drums'")
            if not self.events:
                raise ValueError(f"events must be non-empty when role == '{self.role}'")
        return self

    @model_validator(mode="after")
    def _validate_bars_limit(self) -> "TrackSchema":
        total_bars = _structural_bar_sum(self.events) * self.repeat
        if total_bars > limits.MAX_BARS_PER_TRACK:
            raise ValueError(
                f"track exceeds MAX_BARS_PER_TRACK ({limits.MAX_BARS_PER_TRACK}): "
                f"got {total_bars} bars"
            )
        return self


class PieceSchema(BaseModel):
    title: str | None = None
    bpm: float = Field(gt=0)
    key: str | None = None
    tracks: list[TrackSchema] = Field(min_length=1)

    @field_validator("tracks")
    @classmethod
    def _validate_track_count(cls, v):
        if len(v) > limits.MAX_TRACKS:
            raise ValueError(f"too many tracks: got {len(v)}, MAX_TRACKS is {limits.MAX_TRACKS}")
        return v

    @model_validator(mode="after")
    def _validate_duration(self) -> "PieceSchema":
        seconds = piece_duration_seconds(self)
        if seconds > limits.MAX_DURATION_SECONDS:
            raise ValueError(
                f"piece exceeds MAX_DURATION_SECONDS ({limits.MAX_DURATION_SECONDS}): "
                f"estimated {seconds:.1f}s"
            )
        return self


def piece_duration_seconds(schema: "PieceSchema") -> float:
    """The piece's real playback length in seconds, from its longest track
    (bars * repeat + start_bar), at its bpm."""
    max_bars = 0.0
    for track in schema.tracks:
        if not track.events:
            continue
        track_bars = _structural_bar_sum(track.events) * track.repeat + track.start_bar
        max_bars = max(max_bars, track_bars)
    return max_bars * 4 * 60 / schema.bpm


class ValidationResult(BaseModel):
    valid: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    detected_chords: list[dict] = Field(default_factory=list)
    track_lengths: list[dict] = Field(default_factory=list)
