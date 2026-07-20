---
name: leadsheet
description: Compose real, playable music (chord progressions, bass lines, melodies, drum patterns) as MIDI + an audio preview, via the local leadsheet MCP server. Use whenever the user asks to write a song, chord progression, backing track, melody, drum beat, jingle, or otherwise generate/compose music in any genre or mood.
---

# leadsheet: composing music with the leadsheet MCP server

leadsheet lets you compose real music without writing a single line of
musicpy's operator-heavy Python (`@`, `%`, `^`, `&`, arpeggio index-golf).
You do the musical/creative reasoning -- what chords, what mood, what
instruments, what structure -- and express it as a small JSON object (the
**PieceSchema**, defined below). The `leadsheet` MCP server validates it,
deterministically compiles it into real musicpy objects, cross-checks the
result against musicpy's own chord-theory detector, renders a MIDI file and
an audio preview, and returns everything inline.

**Never write musicpy Python code.** Everything you need to express --
chords, arpeggios, walking bass, drum patterns, melodies -- has a place in
the schema below.

## Workflow

1. If you're unsure a chord name, instrument name, or drum-kit name is
   valid, call `list_capabilities` once per conversation -- it returns the
   live, authoritative lists (161 chord-type aliases, 128 GM instruments,
   drum tokens/kits, valid `style` values per role, and the server's
   guardrail limits) computed straight from musicpy's registries. Don't
   guess a chord suffix's casing (`Fmaj7` is valid, `FMaj7` is not) --
   look it up if in doubt.
2. For anything non-trivial, call `validate` first. It runs structural
   checks plus a semantic cross-check of every chord against musicpy's own
   chord-theory detector, and is much cheaper than a full `compose` (no
   compiling/rendering).
3. Call `compose` with the full `PieceSchema`. If it returns errors, fix
   them and retry -- nothing was compiled or rendered. If it returns
   warnings (e.g. a chord-detection mismatch), read them: they usually mean
   real voicing/enharmonic ambiguity, but reconsider the flagged chord
   before presenting the result to the user.
4. Present the returned audio preview to the user. Keep the returned
   `normalized_schema` in mind for follow-ups.
5. For a follow-up edit ("make it slower", "change the second chord",
   "swap the bass instrument"), use `revise` with a small JSON Merge Patch
   (RFC 7386) against the *previous* `normalized_schema`, rather than
   resending the whole piece. **Important:** RFC 7386 patches replace
   arrays wholesale, they do not merge into array elements -- `tracks` and
   each track's `events` are arrays, so to change one field on one chord
   you must send the complete `tracks` array (copied from the prior
   `normalized_schema`) with just that one field edited, not a
   partial/sparse track object. The `revise` tool's own description
   repeats this with an example.

## The schema (PieceSchema)

Top level:

| field | type | notes |
|---|---|---|
| `title` | string, optional | |
| `bpm` | number, required | must be > 0 |
| `key` | string, optional | e.g. `"A minor"` -- **informational only**, not used by the compiler. It is not enforced -- you must pick chords that are actually in that key yourself. |
| `tracks` | array of Track, required | 1..8 tracks |

Track:

| field | type | notes |
|---|---|---|
| `name` | string, optional | |
| `role` | `"chords" \| "bass" \| "melody" \| "drums" \| "custom"` | required -- drives which `style` values make sense (see below) |
| `instrument` | string or int | GM instrument name (call `list_capabilities` for the list) or 1-128. For `role == "drums"`, this is a **drum-kit name** instead (e.g. `"Standard"`, `"Jazz Kit"`) -- a different registry than melodic instruments. |
| `channel` | int 0-15, optional | omit it -- the server auto-assigns channels and reserves channel 9 for drums. Only set it if you have a specific reason. |
| `start_bar` | number, default 0 | when this track begins, in bars |
| `volume` | int 0-127, optional | applied to the whole track |
| `repeat` | int, default 1 | repeats the whole compiled track (e.g. a 4-note drum pattern with `repeat: 8` to fill 8 bars) |
| `events` | array of Event | required unless `role == "drums"` |
| `drum_pattern` | string | required iff `role == "drums"`; a musicpy drum-pattern string (see Drums below), forbidden otherwise |

Event -- one of three shapes, picked by `type`:

**`ChordEvent`** (`type: "chord"`) -- the main way to write chords/bass:

| field | notes |
|---|---|
| `chord` | a chord symbol, e.g. `"Am7"`, `"Cmaj7"`, `"G7sus4"`, `"C/E"`. Case-sensitive suffix. |
| `octave` | root-pitch octave, default 3 |
| `bars` | required, > 0 -- how many bars this chord spans |
| `style` | see the table below |
| `pattern` | required iff `style == "custom_pattern"`, forbidden otherwise. A list of note indices: `1`, `2`, `3`... = chord tones 1-based; `2.1` = tone 2 up one octave; `-1.2` = tone 1 down two octaves. |
| `subdivision` | e.g. `"1/8"` -- optional override, see per-style defaults below |
| `note_duration` | optional override, see per-style defaults below |
| `velocity` | 0-127, default 100 |

`style` per role (call `list_capabilities` for the exact list, this is the gist):

| style | typical role | what it does | subdivision default | note_duration default |
|---|---|---|---|---|
| `block` | chords | one sustained stab (or a gentle strum if you set `subdivision`) | 0 | subdivision, or `bars` if subdivision is 0 |
| `arpeggio_up` | chords | ascending arpeggio, tiled to fill `bars` | 1/8 | 2x subdivision (legato/overlap) |
| `arpeggio_updown` | chords | up-then-down arpeggio, tiled to fill `bars` | 1/8 | 2x subdivision |
| `custom_pattern` | chords, melody | your own `pattern` list, used verbatim (not tiled) | 1/8 | 2x subdivision |
| `root_only` | bass | single sustained root note | n/a (= `bars`) | n/a |
| `root_fifth` | bass | alternating root/fifth, the classic bass pattern | `bars`/2 | = subdivision |
| `walking` | bass | deterministic root-third-fifth-approach walking line (not random) | `bars`/4 | = subdivision |

**`NoteEvent`** (`type: "note"`) -- a single note or rest:

| field | notes |
|---|---|
| `note` | e.g. `"E5"` -- required unless `rest: true` |
| `duration` | required, e.g. `"1/4"` or `0.25` |
| `rest` | if true, this is a rest of `duration` bars |
| `velocity` | 0-127, default 100 |

Verbose for a whole melody line -- prefer `RawEvent` for melody (below).

**`RawEvent`** (`type: "raw"`) -- musicpy's native note-string mini-language,
passed through verbatim: `notes: "E5[.4;.4], r[.4], C5[.4;.4], D5[.4;.4]"`.
**This is the recommended way to write melody tracks** -- chord-symbol
events flatten everything to chord tones, which can't express real melodic
motion. Full syntax reference: `references/note-string-syntax.md` in this
skill (read it when you need it, don't try to write melody from memory).

### Drums

`drum_pattern` is a comma/`|`-separated string of drum tokens from
`list_capabilities`' `drum_tokens` (e.g. `K` = kick, `H` = closed hi-hat,
`S` = snare, `S2` = alt snare, `OH` = open hi-hat, `C`/`C2` = crash/ride).
Example: `"K, H, S, H, K, H, S, H"` for a basic 8th-note beat over 1 bar.
Use `repeat` to tile a short pattern across the whole piece (e.g. an 8-bar
piece with a 1-bar, 4-token pattern needs `repeat: 8`).

## Music theory guidance

- `key` is informational only -- the compiler does not constrain your chord
  choices to it. You are responsible for picking chords that are actually
  in-key (or deliberately, tastefully out of key).
- Common progressions by feel:
  - jazzy/lo-fi/melancholic: `vi-ii-V-I` (e.g. Am7-Dm7-G7-Cmaj7), or add a
    `IV-iii` turnaround (Fmaj7-Em7) before resolving back to `vi`.
  - upbeat pop: `I-V-vi-IV` (e.g. C-G-Am-F).
  - moody/minor: `i-VI-III-VII` (e.g. Am-F-C-G, natural minor).
  - blues: `I7-IV7-I7-V7-IV7-I7` (dominant 7ths throughout).
- Role-to-style pairing that reads as a real arrangement: chords track ->
  `block` or `arpeggio_updown`; bass track -> `root_fifth` or `walking`;
  melody track -> `RawEvent` note-strings; drums -> a short `drum_pattern`
  with `repeat` to fill the piece.
- 7th/9th/sus chords read as far more "produced" than plain triads --
  reach for `maj7`/`m7`/`7`/`sus4`/`add9` etc. rather than bare major/minor
  unless the user asked for something simple/folky.

## Worked example: lo-fi progression (validated end-to-end -- compiles,
renders, and passes the chord-theory cross-check with zero warnings)

```json
{
  "title": "lofi study break",
  "bpm": 85,
  "key": "A minor",
  "tracks": [
    {
      "name": "chords",
      "role": "chords",
      "instrument": "Electric Piano 1",
      "events": [
        {"type": "chord", "chord": "Am7", "octave": 3, "bars": 1, "style": "arpeggio_updown"},
        {"type": "chord", "chord": "Dm7", "octave": 3, "bars": 1, "style": "arpeggio_updown"},
        {"type": "chord", "chord": "G7", "octave": 3, "bars": 1, "style": "arpeggio_updown"},
        {"type": "chord", "chord": "Cmaj7", "octave": 3, "bars": 1, "style": "arpeggio_updown"},
        {"type": "chord", "chord": "Fmaj7", "octave": 3, "bars": 1, "style": "arpeggio_updown"},
        {"type": "chord", "chord": "Em7", "octave": 3, "bars": 1, "style": "arpeggio_updown"},
        {"type": "chord", "chord": "Am7", "octave": 3, "bars": 1, "style": "arpeggio_updown"},
        {"type": "chord", "chord": "G7sus4", "octave": 3, "bars": 1, "style": "arpeggio_updown"}
      ]
    },
    {
      "name": "bass",
      "role": "bass",
      "instrument": "Acoustic Bass",
      "events": [
        {"type": "chord", "chord": "Am7", "octave": 2, "bars": 1, "style": "root_fifth"},
        {"type": "chord", "chord": "Dm7", "octave": 2, "bars": 1, "style": "root_fifth"},
        {"type": "chord", "chord": "G7", "octave": 2, "bars": 1, "style": "root_fifth"},
        {"type": "chord", "chord": "Cmaj7", "octave": 2, "bars": 1, "style": "root_fifth"},
        {"type": "chord", "chord": "Fmaj7", "octave": 2, "bars": 1, "style": "root_fifth"},
        {"type": "chord", "chord": "Em7", "octave": 2, "bars": 1, "style": "root_fifth"},
        {"type": "chord", "chord": "Am7", "octave": 2, "bars": 1, "style": "root_fifth"},
        {"type": "chord", "chord": "G7sus4", "octave": 2, "bars": 1, "style": "root_fifth"}
      ]
    },
    {
      "name": "melody",
      "role": "melody",
      "instrument": "Flute",
      "events": [
        {"type": "raw", "notes": "E5[.4;.4], r[.4], C5[.4;.4], D5[.4;.4], E5[.2;.2], r[.4], A4[.4;.4], C5[.4;.4], B4[.2;.2], r[.2], G4[.4;.4], A4[.4;.4], B4[.4;.4], C5[.2;.2], r[.2], A4[.2;.2], G4[.2;.2], E4[.2;.2]"}
      ]
    },
    {
      "name": "drums",
      "role": "drums",
      "instrument": "Standard",
      "drum_pattern": "K, H, S, H",
      "repeat": 8
    }
  ]
}
```

## Worked example: upbeat pop progression, block chords + walking bass

```json
{
  "bpm": 118,
  "tracks": [
    {
      "role": "chords",
      "instrument": "Acoustic Grand Piano",
      "events": [
        {"type": "chord", "chord": "C", "bars": 1, "style": "block", "subdivision": "1/4"},
        {"type": "chord", "chord": "G", "bars": 1, "style": "block", "subdivision": "1/4"},
        {"type": "chord", "chord": "Am", "bars": 1, "style": "block", "subdivision": "1/4"},
        {"type": "chord", "chord": "F", "bars": 1, "style": "block", "subdivision": "1/4"}
      ]
    },
    {
      "role": "bass",
      "instrument": "Electric Bass (finger)",
      "events": [
        {"type": "chord", "chord": "C", "octave": 2, "bars": 1, "style": "walking"},
        {"type": "chord", "chord": "G", "octave": 2, "bars": 1, "style": "walking"},
        {"type": "chord", "chord": "Am", "octave": 2, "bars": 1, "style": "walking"},
        {"type": "chord", "chord": "F", "octave": 2, "bars": 1, "style": "walking"}
      ]
    }
  ]
}
```

## Worked example: a custom_pattern arpeggio and a NoteEvent rest

```json
{
  "bpm": 100,
  "tracks": [
    {
      "role": "chords",
      "instrument": "Electric Piano 1",
      "events": [
        {
          "type": "chord", "chord": "Cmaj7", "bars": 1, "style": "custom_pattern",
          "pattern": [1, 2, 3, 4, 3.1, 2.1, 1.1],
          "subdivision": "1/8"
        }
      ]
    },
    {
      "role": "melody",
      "instrument": "Violin",
      "events": [
        {"type": "note", "note": "E5", "duration": "1/4"},
        {"type": "note", "duration": "1/8", "rest": true},
        {"type": "note", "note": "G5", "duration": "1/4"}
      ]
    }
  ]
}
```

## Non-instructions

- Never write musicpy Python code directly, and never use the
  `[duration;interval;volume]` note-string mini-language anywhere except
  inside a `RawEvent.notes` string.
- Never guess a chord-type suffix's casing or a GM instrument/drum-kit
  spelling -- call `list_capabilities` if unsure.
- Don't put a `pattern` field on a `ChordEvent` unless `style ==
  "custom_pattern"` -- it's a hard validation error otherwise.
- Don't set `channel: 9` on anything except a `role: "drums"` track.
- `key` does not constrain the compiler -- don't rely on it to keep you
  in-key; choose the chords yourself.
