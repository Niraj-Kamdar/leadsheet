# The raw: note-string mini-language

This is musicpy's own note-string syntax, valid **only** after a B2 melody
track's `raw:` keyword (e.g. `melody "Flute" raw: E5[.4;.4], r[.4]`). It is
the recommended way to write melody tracks, since chord-symbol events can
only produce chord tones and can't express real melodic motion.

## Basic shape

A comma-separated list of notes, each optionally followed by
`[duration;interval;volume]`:

```
"G5[3/4;3/4], F5[1/8;1/8], E5[1/8;1/8]"
```

- **duration**: how long the note rings, in bars (whole note = 1.0).
- **interval**: time from this note's onset to the *next* note's onset, in
  bars. Not "gap after" -- if interval < duration, notes overlap (legato).
- **volume**: optional third field, 0-127.
- You can specify just duration, duration+interval, or all three. Omitted
  trailing brackets fall back to the string's `default_duration`/
  `default_interval` (both default to 1/8 bar if not otherwise set).

## Shorthand

- `.n` means `1/n`: `.8` = 1/8, `.4` = 1/4, `.2` = 1/2, `.16` = 1/16.
  Non-power-of-two durations are written as plain fractions: `3/4`, `5/8`.
- When interval equals duration, abbreviate the interval as `.`:
  `G5[3/4;.]` means duration=3/4, interval=3/4.

Combined example:

```
"G5[3/4;3/4], F5[.8;.8], E5[.8;.8], F5[3/4;.3/4], E5[.8;.8], D5[.8;.8], E5[.4;.4], D5[.4;.4], C5[.2;.2], B4[.2;.2], G4[.2;.2]"
```

## Rests

`r[duration]` inserts a rest of `duration` bars. The nth-note shorthand
works here too: `r[.4]` = a 1/4-bar rest.

```
"E5[.4;.4], r[.4], C5[.4;.4], D5[.4;.4]"
```

## Continuation (tied notes)

`-[duration;interval]` extends the *previous* note's duration and interval
by the given amount, instead of starting a new note (a tie):

```
"C5[1/4;1/4], -[1/4;1/4], D5[1/4;1/4]"
```
This produces a C5 that rings for 1/2 a bar (tied across two 1/4-bar
segments), then a D5 -- not three separate notes.

## Simultaneous notes (chords within a note-string)

Join note names with `;` to play them at once: `C5;E5;G5` is a C major
triad voiced exactly as written (no chord-symbol normalization -- you're
specifying the exact pitches).

## Relative pitch (stretch feature -- optional, use sparingly)

Once at least one absolute pitch has been given, later notes can be
written as semitone offsets from the previous note:

- `+n` : previous note raised by n semitones (reference note for further
  relative moves does *not* change)
- `++n` : previous note raised by n semitones, and becomes the new
  reference note for subsequent relative moves
- `+no` : previous note raised by n octaves; `+nom` : raised n octaves
  then m semitones (also has a `++` variant)
- Use `-` in place of `+` for downward motion
- `C4(+n)` (or `C4(-n)`) means "n semitones above (or below) C4", usable
  as a standalone absolute-ish reference

```
"A#4, +7, +10, +1o2, +1o3"
```

This is rarely necessary -- prefer absolute pitches (`C5`, `A4`, etc.)
unless you have a specific reason to write a pattern relative to a moving
reference tone.
