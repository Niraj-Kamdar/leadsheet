---
name: leadsheet
description: Compose real, playable music (chord progressions, bass lines, melodies, drum patterns) and save it as a tagged mp3, via the local leadsheet MCP server. Use whenever the user asks to write a song, chord progression, backing track, melody, drum beat, jingle, or otherwise generate/compose music in any genre or mood.
---

# leadsheet: composing music with the leadsheet MCP server

leadsheet lets you compose real music without writing a single line of
musicpy's operator-heavy Python (`@`, `%`, `^`, `&`, arpeggio index-golf).
You do the musical/creative reasoning -- what chords, what mood, what
instruments, what structure -- and write it as a compact line-oriented DSL
(**B2**, defined below) in a `.leadsheet` file. The `leadsheet` MCP server
reads that file, validates it, deterministically compiles it into real
musicpy objects, cross-checks the result against musicpy's own chord-theory
detector, renders a tagged mp3 preview, and saves it to disk.

**Never write musicpy Python code.** Everything you need to express --
chords, arpeggios, walking bass, drum patterns, melodies -- has a place in
the B2 grammar below.

## Workflow

1. If you're unsure a chord name, instrument name, or drum-kit name is
   valid, call `list_capabilities` once per conversation -- it returns the
   live, authoritative lists (161 chord-type aliases, 128 GM instruments,
   drum tokens/kits, valid `style` values per role, and the server's
   guardrail limits) computed straight from musicpy's registries. Don't
   guess a chord suffix's casing (`Fmaj7` is valid, `FMaj7` is not) --
   look it up if in doubt.
2. Write the piece as B2 text (see below) to a `.leadsheet` file with your
   own Write tool.
3. For anything non-trivial, call `validate(path=...)` first. It runs
   structural checks plus a semantic cross-check of every chord against
   musicpy's own chord-theory detector, and is much cheaper than a full
   `compose` (no compiling/rendering). It always returns `track_lengths`
   (every non-drum track's real computed bar length) -- glance at it
   whenever tracks are meant to line up (e.g. a melody that should span the
   same 8 bars as the chords underneath it); a hand-tallied `notes:` track's
   duration is easy to get wrong and nothing else will catch a drift. Use a
   `bars=<n>` header modifier (see below) to turn that into a hard error
   instead of something you have to notice yourself.
4. Call `compose(path=...)`. If it returns `{"ok": false, "errors": [...]}`,
   fix the `.leadsheet` file and retry -- nothing was compiled, rendered, or
   saved. If it returns warnings (e.g. a chord-detection mismatch), read
   them: they usually mean real voicing/enharmonic ambiguity, but reconsider
   the flagged chord before presenting the result to the user.
5. On success, `compose` has already rendered, tagged, and saved an mp3 --
   its path is in the result (`{"ok": true, "path": "...", "warnings": []}`),
   next to the `.leadsheet` file by default, or under `output_dir` if you
   passed one. There's no separate save step and nothing to run by hand --
   just tell the user where the file landed.
6. For a follow-up edit ("make it slower", "change the second chord", "swap
   the bass instrument"), edit the same `.leadsheet` file with your Edit
   tool -- a precise, targeted change -- and call `compose(path=...)` again.
   There is no `revise` tool and no merge-patch mechanism; the file on disk
   is always the source of truth.

## The B2 DSL

Line-oriented, one statement per line, distinguished by its first token.
Field *values* are always spelled out in full (`oct=2`, `subdiv=1/8`, never
a glued shorthand) -- terser field *names* are fine, ambiguous field
*values* are not.

### 1. Top-level line (exactly one, first non-blank line)

```
bpm=<number> [title="<string>"] [key="<string>"]
```
`bpm` is required; `title`/`key` are optional. `key` (e.g. `"A minor"`) is
**informational only** -- it is not enforced, you must pick chords that are
actually in that key yourself.

### 2. Track header line

```
<role> "<instrument>" [name="<string>"] [start=<bar>] [vol=<0-127>] [repeat=<n>] [bars=<n>] ...
```
- `role` is one of `chords | bass | melody | drums | custom`, bare and
  unquoted -- drives which `style` values make musical sense, but doesn't
  otherwise restrict what a track can contain.
- `instrument` is the **full canonical GM instrument name or drum-kit
  name** (e.g. `"Distortion Guitar"`, `"Power Kit"`), quoted because it may
  contain spaces/parens -- call `list_capabilities` if unsure of the exact
  spelling. An int (1-128) also works, unquoted.
- `name=`, `start=`, `vol=`, `repeat=` are all optional: track name, the bar
  it starts on (default 0), track volume (0-127), and how many times to
  repeat the whole compiled track (e.g. a 1-bar 4-token drum pattern with
  `repeat=8` to fill 8 bars).
- `bars=<n>` (optional, not valid on `drums` tracks) asserts this track's
  events should sum to exactly `n` bars -- `validate`/`compose` hard-error
  with the real computed length if they don't, instead of silently
  compiling something shorter/longer than intended. Cheap insurance on any
  track whose length matters relative to its siblings (e.g. a countermelody
  that must span the same 8 bars as the chords under it).
- What follows the header modifiers depends on the track's content -- see
  the forms below. A header line always ends with exactly one `:`.

**Chord-list segment** (chords/bass/melody/custom tracks) -- a run of
chord events sharing one style/modifiers:

```
<role> "<instrument>" [header modifiers] [style] [subdiv=<frac>] [oct=<n>] [pattern=[<index-list>]] [vel=<0-127>]: <chord-list>
```
- `style` is one of `block | arpeggio_up | arpeggio_updown | custom_pattern
  | root_only | root_fifth | walking`, bare -- omit for the schema default
  (`block`).
- `subdiv=`, `oct=`, `vel=` apply to every chord in the list. `pattern=[...]`
  (only with `style=custom_pattern`) is a literal note-index list, e.g.
  `pattern=[1,2,1,1,2,1,1,2]` (`1`,`2`,`3`... = chord tones 1-based; `2.1` =
  tone 2 up an octave; `-1.2` = tone 1 down two octaves).
- `<chord-list>` is a space-separated list of bare chord symbols (`Am7`,
  `Cmaj7`, `F5(+octave)`, `C/E`) -- every chord gets 1 bar by default.
  - Append `*<bars>` to override that for one chord, e.g. `Am7*0.5` for a
    half-bar harmonic push, or `C*2` for a chord that rings two bars --
    a plain decimal or an `<a>/<b>` fraction, either works.
  - The bare token `r` (optionally `r*<bars>`) is a **rest**: silence for
    that duration instead of a chord. Use it to make a chords/brass/custom
    track punctuate sparsely (hit, then go quiet) instead of faking
    silence with volume or register.
- If the track's events aren't style-homogeneous (e.g. 8 bars of
  `custom_pattern` chug, then 4 bars of ringing `block` chords), end the
  header in a bare `:` with nothing after it, then follow with one or more
  indented **segment lines**, each its own `[style] [modifiers]: <chord-list>`
  -- they concatenate in order. See the Metal example below.
- Melody tracks can use this same chord-list mechanism too (an arpeggiated
  lead line is just a chords-style track with `role=melody`) -- see
  Chiptune/EDM in `references/genre-recipes.md`.

**Drum line** (`role=drums` only, always a single line, never segments):

```
drums "<kit name>" [name=...] [start=...] [repeat=...]: <token-list>
```
`<token-list>` is a comma-separated list of drum tokens from
`list_capabilities` (`K` = kick, `H` = closed hi-hat, `S`/`S2` = snare/alt
snare, `OH` = open hi-hat, `C`/`C2` = crash/ride, `0` = rest), e.g.
`K, H, S, H` for a basic 8th-note beat over 1 bar.

**Melody lines** -- `notes:`, B2's own native melody grammar. Usable both as
a track header's single inline segment and as an ordinary segment line, so
a melody track can mix an arpeggio section with a written-phrase section
under one header, exactly like chord-list tracks already mix segments.

```
notes [dur=<fraction>] [int=<fraction>] [vel=<0-127>]: <token> <token> ...
```

`dur=`/`int=`/`vel=` are segment-level defaults. Each space-separated token
is one of:

| Token | Meaning |
|---|---|
| `E5` | note at segment defaults (`dur=` is required if not set at segment level; `int=` defaults to `dur`; `vel=` defaults to segment `vel=` or 100) |
| `E5@1/4` | duration override for this note -- interval equals duration for an `@`-overridden note, superseding a segment `int=` |
| `r` / `r@1/8` | rest, at segment default or overridden duration |
| `C5+E5+G5@1/2` | simultaneous notes (chord stab / double-stop) -- `+`-joined pitch group; an `@` override applies to the whole group |
| `E5 x8` | repeat the immediately preceding token (note, rest, or stack) 8 times total |

Legato/staccato (`int` different from `dur`) and per-note velocity accents
are segment-level `int=`/`vel=` plus a second segment line for the outlier
-- not per-token syntax.

```
melody "Violin" notes: E5@1/4 r@1/8 G5@1/4
melody "Flute" notes dur=1/4: E5 r C5 D5 E5@1/2 r A4 C5
melody "Piano" notes dur=1/2 vel=90: C5+E5+G5
melody "Lead 1 (square)" notes dur=1/16: E5 x8 G5 x8
```

**Macros** -- define a phrase once, reuse it anywhere in the file (a
different track, a different instrument, later in the piece):

```
define <name> [style] [subdiv=<frac>] [oct=<n>] [pattern=[<index-list>]] [vel=<0-127>]: <chord-list>
define <name> notes [dur=<frac>] [int=<frac>] [vel=<0-127>]: <token> <token> ...
define <name>: <token-list>          # inferred as a drum pattern -- see below
```
- `<name>` is a bare identifier (letters/digits/underscore), and `define`
  only makes sense between tracks (not inside an open multi-segment track).
  Its content is exactly one of the shapes above -- whichever a track
  header could use in that position -- captured verbatim, including any
  style/modifiers. A plain `K, H, S, H`-shaped comma list (no style prefix)
  is inferred as a drum pattern, since chord-lists are always
  space-separated and drum-token-lists are always comma-separated.
  **Important**: don't put a `:` right after `<name>` unless the content is
  a bare chord-list -- `define riff notes: ...` (no colon on the name), not
  `define riff: notes: ...` (that `:` ends the header before `notes:` is
  ever seen). Only `define <name>:` (name directly colon-terminated) is
  correct when there's no style/notes keyword, e.g. `define riff: C G Am F`.
- `use: <name> [x<n>] [transpose=<semitones>] [vel=<0-127>]` replays that
  captured content wherever a chord-list segment could go: inline on a
  track header, as one of several segment lines, or as a `drums` track's
  token list. `x<n>` (default 1) repeats the expansion -- for a drum
  pattern that's the token list repeated, for everything else it's the
  events repeated. `transpose=<semitones>` shifts every literal pitch in
  the expansion (chord roots and melody notes alike) by that many
  semitones before it's emitted -- how a reprised motif becomes a sequence
  or a harmony line without redefining it; not valid on a drum-pattern
  macro. `vel=<0-127>` overrides velocity for this particular use, without
  redefining the macro. Kind-checked against where it's used (a
  drum-pattern macro only works in a `drums` position, everything else
  only works in a non-`drums` position); using an undefined name is a clear
  error. No nested macros -- a `define` body can't itself `use:` another
  macro.
  ```
  define villain_motif notes dur=1: C4 Eb4 G4
  melody "Trumpet" name="villain (brass)" start=16 use: villain_motif
  melody "Violin" name="villain (strings)" start=32 use: villain_motif x2
  melody "Violin" name="villain (sequence, down a third)" start=48 use: villain_motif transpose=-3
  ```
  This is how a reprised motif on a different instrument, or an escalating
  drum groove across sections, stays a one-line reference instead of being
  retyped in full every time it recurs.

**`section`** -- a named group of track-fragments, re-triggerable as a unit
at a new bar offset. This is the fix for "a chorus is 4 tracks moving
together, not one track's pattern":

```
section <name>:
  <role> "<instrument>" [header modifiers] ...: <content>
  ...

use section <name> start=<bar>
```
- Each fragment line under `section <name>:` is a complete, self-contained
  track header -- multi-segment tracks (a header ending in a bare `:`
  followed by indented segment lines) aren't supported inside a `section`
  block; write the fragment as one line, or move it out of the section.
- `use section <name> start=<bar>` duplicates every fragment defined in the
  section into the piece's tracks, each offset by `start=` (added to the
  fragment's own `start=`, which defaults to 0). Purely additive to the
  existing tracks -- no new relationship between tracks is introduced
  beyond what independent `start=` values already express. Call it more
  than once (with different `start=`) to place the same section at several
  points in the piece.
  ```
  section chorus:
    chords "Electric Piano 1" block: Fmaj7 C G Am
    bass "Acoustic Bass" root_fifth oct=2: Fmaj7 C G Am
    drums "Standard" repeat=4: K, H, S, H
    melody "Flute" notes dur=1/4: F5 A5 C5 x2 A5 F5

  use section chorus start=8
  use section chorus start=24
  ```

`style` per role (call `list_capabilities` for the exact list, this is the gist):

| style | typical role | what it does | subdiv default | note-length default |
|---|---|---|---|---|
| `block` | chords | one sustained stab (or a gentle strum if you set `subdiv=`) | 0 | subdiv, or the chord's own bar count if subdiv is 0 |
| `arpeggio_up` | chords, melody | ascending arpeggio, tiled to fill the bar | 1/8 | 2x subdiv (legato/overlap) |
| `arpeggio_updown` | chords, melody | up-then-down arpeggio, tiled to fill the bar | 1/8 | 2x subdiv |
| `custom_pattern` | chords, melody | your own `pattern=` list, used verbatim (not tiled) | 1/8 | 2x subdiv |
| `root_only` | bass | single sustained root note | n/a | n/a |
| `root_fifth` | bass | alternating root/fifth, the classic bass pattern | half the bar | = subdiv |
| `walking` | bass | deterministic root-third-fifth-approach walking line (not random) | quarter the bar | = subdiv |

### Worked example: Metal (the hardest case in the corpus -- multi-section, doubled track, mid-track style switch, staggered entrance)

```
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
```
Every technique for longer, multi-section pieces falls out of the mechanisms
above: a track's events just concatenate in order (verse-then-chorus is one
track's segment lines back to back), a doubled/thickened layer is a second
track with the same chord list at a different `oct=`, a lead entering partway
through is `start=<bar>` on its own track, and section-specific drum grooves
are separate `drums` lines with their own `start=`. See
`references/genre-recipes.md` for more genre-specific instrument picks and
`style`/`pattern=` tricks.

## Music theory guidance

- `key=` is informational only -- the compiler does not constrain your chord
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
  melody track -> a `notes:` phrase; drums -> a short drum-token list
  with `repeat=` to fill the piece.
- 7th/9th/sus chords read as far more "produced" than plain triads --
  reach for `maj7`/`m7`/`7`/`sus4`/`add9` etc. rather than bare major/minor
  unless the user asked for something simple/folky.
- For genre-specific instrument picks, `style`/`pattern=` tricks (e.g. metal's
  palm-muted power-chord chug, chiptune's fast arpeggios, reggaeton's dembow
  drum pattern), and validated worked examples covering rock, metal,
  chiptune/8-bit/16-bit/retro, acoustic guitar, pop, lo-fi, reggaeton, and
  EDM, see `references/genre-recipes.md` in this skill -- read the relevant
  section before composing in one of those genres rather than guessing at
  instrument names or drum patterns from memory.

## Worked example: lo-fi progression (validated end-to-end -- compiles,
renders, and passes the chord-theory cross-check with zero warnings)

```
bpm=85 title="lofi study break" key="A minor"
chords "Electric Piano 1" name="chords" arpeggio_updown oct=3: Am7 Dm7 G7 Cmaj7 Fmaj7 Em7 Am7 G7sus4
bass "Acoustic Bass" name="bass" root_fifth oct=2: Am7 Dm7 G7 Cmaj7 Fmaj7 Em7 Am7 G7sus4
melody "Flute" name="melody" notes dur=1/4: E5 r C5 D5 E5@1/2 r A4 C5 B4@1/2 r@1/2 G4 A4 B4 C5@1/2 r@1/2 A4@1/2 G4@1/2 E4@1/2
drums "Standard" name="drums" repeat=8: K, H, S, H
```

## Worked example: upbeat pop progression, block chords + walking bass

```
bpm=118
chords "Acoustic Grand Piano" block subdiv=1/4: C G Am F
bass "Electric Bass (finger)" walking oct=2: C G Am F
```

## Worked example: a custom_pattern arpeggio and a note rest

```
bpm=100
chords "Electric Piano 1" custom_pattern pattern=[1,2,3,4,3.1,2.1,1.1] subdiv=1/8: Cmaj7
melody "Violin" notes: E5@1/4 r@1/8 G5@1/4
```

## Worked example: cinematic cue -- sub-bar chords, a rest, bars=, and a reused motif

Orchestral/cinematic writing is the case that motivated `*<bars>`, the `r`
rest token, `bars=`, and `define`/`use`: a half-bar harmonic push, brass
that punctuates instead of sustaining, and a short villain motif stated on
one instrument and restated (doubled, longer) on another later on. Compiles
and renders with zero warnings; `compose`'s `track_lengths` for this piece
confirms the two `bars=4` tracks really are 4 bars, and shows the two motif
statements at 3 and 6 bars (3 notes once, 3 notes twice) without having to
count note tokens by hand.

```
bpm=90 title="battle cue"
define villain_motif notes dur=1: C4 Eb4 G4
chords "Pad 3 (polysynth)" bars=4 block: Cm*0.5 r*0.5 Ab*2 Eb
custom "Trumpet" name="stab" bars=4 block: r*3 Cm*1
melody "Electric Guitar (clean)" name="motif (lead)" start=4 use: villain_motif
custom "Viola" name="motif (strings, doubled)" start=4 use: villain_motif x2
```

## Non-instructions

- Never write musicpy Python code directly -- everything melodic goes
  through `notes:` (B2's own melody grammar), never a musicpy note-string.
- Never guess a chord-type suffix's casing or a GM instrument/drum-kit
  spelling -- call `list_capabilities` if unsure.
- Don't set `pattern=[...]` on a segment unless its `style` is
  `custom_pattern` -- it's a hard validation error otherwise.
- `key=` does not constrain the compiler -- don't rely on it to keep you
  in-key; choose the chords yourself.
- Don't try to hand-roll a merge-patch or partial update -- there is no
  `revise` tool. Edit the `.leadsheet` file directly and call `compose`
  again.
- Don't put a `:` right after a macro's `<name>` in `define` if its content
  is `notes:`/a styled chord-list -- that `:` becomes the header terminator
  before the real content keyword is ever seen (`define riff notes: ...`,
  not `define riff: notes: ...`; see Macros above).
- `bars=<n>` isn't valid on a `drums` track -- there's no `events` list for
  it to check against.
- A `section` block only takes complete, single-line track fragments --
  don't open a multi-segment track (a header ending in a bare `:`) inside
  one.
