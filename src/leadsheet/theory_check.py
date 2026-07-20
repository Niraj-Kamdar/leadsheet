"""Structural validation (Pydantic) + semantic/theory validation
(musicpy's own chord-type detector cross-check), combined into the
ValidationResult shared by the `validate` and `compose` tools.
"""

from __future__ import annotations

import musicpy as mp
from musicpy import database
from pydantic import ValidationError

from leadsheet import capabilities
from leadsheet.schema import ChordEvent, PieceSchema, ValidationResult


def _format_pydantic_errors(exc: ValidationError) -> list[str]:
    formatted = []
    for err in exc.errors():
        field_path = ".".join(str(part) for part in err["loc"])
        formatted.append(f"{field_path}: {err['msg']}" if field_path else err["msg"])
    return formatted


def _chord_family_for_symbol(root: str, suffix: str) -> tuple[str, ...] | None:
    # trans() treats a bare root with no suffix as an implicit major chord.
    return capabilities.chord_family_of(suffix if suffix else "M")


def check_chord_event(track_index: int, event_index: int, event: ChordEvent) -> tuple[dict, str | None]:
    """Cross-checks one ChordEvent's root-position voicing against
    musicpy's own detect_chord_type. Returns (detected_chords entry,
    warning message or None)."""
    root_chord = mp.C(event.chord, event.octave)
    detected = mp.alg.detect_chord_type(root_chord, get_chord_type=True)

    split = capabilities.split_chord_symbol(event.chord.split("/")[0])
    intended_root, intended_suffix = split if split else (None, "")

    match = False
    detected_str = None
    if detected.chord_type is not None:
        detected_str = detected.get_root_position()
        detected_root_degree = database.standard.get(detected.root)
        intended_root_degree = database.standard.get(intended_root) if intended_root else None
        root_match = (
            detected_root_degree is not None and detected_root_degree == intended_root_degree
        )
        detected_family = capabilities.chord_family_of(detected.chord_type)
        intended_family = _chord_family_for_symbol(intended_root or "", intended_suffix)
        suffix_match = detected_family is not None and detected_family == intended_family
        match = root_match and suffix_match

    entry = {
        "track": track_index,
        "event": event_index,
        "intended": event.chord,
        "detected": detected_str,
        "match": match,
    }
    warning = None
    if not match:
        warning = (
            f"track {track_index} event {event_index}: requested chord "
            f"'{event.chord}' but musicpy's chord-type detector reports "
            f"'{detected_str}' -- this can be legitimate voicing/enharmonic "
            "ambiguity, but reconsider the chord if it wasn't intended."
        )
    return entry, warning


def check_semantics(schema: PieceSchema) -> tuple[list[str], list[dict]]:
    warnings: list[str] = []
    detected_chords: list[dict] = []
    for t_idx, track in enumerate(schema.tracks):
        if not track.events:
            continue
        for e_idx, event in enumerate(track.events):
            if isinstance(event, ChordEvent):
                entry, warning = check_chord_event(t_idx, e_idx, event)
                detected_chords.append(entry)
                if warning:
                    warnings.append(warning)
    return warnings, detected_chords


def validate(schema_dict: dict) -> ValidationResult:
    try:
        schema = PieceSchema(**schema_dict)
    except ValidationError as exc:
        return ValidationResult(valid=False, errors=_format_pydantic_errors(exc))

    warnings, detected_chords = check_semantics(schema)
    return ValidationResult(valid=True, warnings=warnings, detected_chords=detected_chords)
