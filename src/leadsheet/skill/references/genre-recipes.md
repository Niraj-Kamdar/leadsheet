# Genre recipes

Concrete starting points -- instruments, progressions, `style`/`pattern=`
tricks, and drum patterns -- for genres that don't fall out obviously from
the general schema guidance in `SKILL.md`. Every full B2 example below
round-trips to the exact `PieceSchema` this repo already validated
end-to-end (`validate`/`compose` both passed -- a couple of power-chord ones
return a specific, expected warning -- explained under Rock/Metal). Read the
relevant section when composing in that genre; don't try to reconstruct
these from memory.

Instrument names/numbers and drum-kit names are quoted verbatim from
`list_capabilities` -- use the string form (e.g. `"Distortion Guitar"`), the
numbers here are just so you recognize them in `list_capabilities` output.

Beyond the snippets below, the `examples/` directory alongside this repo's
`src/` and `tests/` holds a further corpus of full, validated `.leadsheet`
files -- one per genre/technique, each parsed, schema-checked, theory-checked,
and compiled end-to-end as part of the test suite (`tests/test_examples_corpus.py`).
They're adapted from (not verbatim transcriptions of) the reference
compositions in musicpy's own docs -- reach for one directly, with your Read
tool, when a genre or technique below is too thin, or isn't covered at all
(doom metal, horror/suspense orchestral, non-linear harp arpeggios, ambient
pads, lydian-borrowed jazz-pop, a verse/chorus multi-section arrangement, an
extreme-tempo four-on-the-floor loop, and a `section`+`define`/`use`-driven
piece are all covered there -- see the per-genre notes below for which file
goes with which).

## Quick lookup

| genre | bpm | drum kit | signature move |
|---|---|---|---|
| Rock | 120-145 | `Power Kit` | power-chord `block`, driving 8th-note beat |
| Metal | 90-160 (doom: 25-70) | `Power Kit` or `Standard` | power-chord chug via `custom_pattern` |
| Chiptune / 8-bit / 16-bit / retro | 120-160 | `Electronic Kit` | `Lead 1 (square)` + `arpeggio_up` at `1/16` |
| Guitar-driven / acoustic | 80-110 | none, or `Brush Kit` | fingerstyle `custom_pattern` on nylon/steel guitar |
| Pop | 100-128 | `Standard` or `Room Kit` | `block`/`arpeggio_updown` chords, see SKILL.md's pop example |
| Lo-fi | 70-90 | `Jazz Kit` | see SKILL.md's worked lo-fi example |
| Reggaeton | 88-96 | `TR-808 Kit` | dembow drum pattern, minor-loop chords |
| EDM | 122-130 | `Electronic Kit` | four-on-the-floor kick, sawtooth lead arpeggio |
| Cinematic / orchestral | 60-100 (varies a lot by cue) | sparse, or none | sub-bar chords (`*<bars>`), chord/brass rests (`r`), motif reuse via `define`/`use` |
| Ambient / new-age | 70-90 | none | sustained `maj9`/`m9` pads, low velocity, sparse melody |
| Jazz-pop (borrowed/lydian color) | 90-110 | none, or light brush | slash chords (`Cmaj7/E`), `walking` bass, stepwise melody |
| Hardcore / speedcore / gabber | 250-300+ | `TR-808 Kit` or `Electronic Kit` | four-on-the-floor at an extreme bpm, keep bars short |

See `examples/doom-metal-dirge.leadsheet` for doom metal's ultra-slow end
(bpm 25-70, under the Metal row above) and `examples/horror-suspense-orchestral.leadsheet`
/ `examples/orchestral-harp-cascade.leadsheet` for two more cinematic/orchestral
techniques (eerie tension, non-linear harp arpeggios), all discussed under
their respective sections below.

## Structuring longer, multi-section pieces

Every genre example below is one short loop -- deliberately, so it's easy to
read. But the musicpy docs' own reference compositions (a J-rock intro, a
full Yui cover, an 8-bit game theme) are all several sections long, with
layered, doubled, and independently-varying parts, not a single 4-bar loop.
Nothing about this grammar limits you to a loop -- the same few techniques
those docs pieces use are directly available here:

- **Multi-section arrangements are just more segment lines.** A track's
  events concatenate in the order given, so "verse then chorus" is simply
  the verse's segment line(s) followed by the chorus's segment line(s) under
  the same track header -- no special section/marker concept needed. Give
  the chorus louder `vel=`, bigger chords (e.g. `"5(+octave)"` instead of
  `"5"`), or a different `style` (e.g. verse `custom_pattern` chug -> chorus
  ringing `block`) so it actually reads as a lift, not just "more of the
  same chords."
- **Doubling/thickening a riff** (the source docs' doom-metal and
  scary-atmosphere examples both layer the same line an octave apart, e.g.
  musicpy's `a | a - 2`) maps here to a **second track** with the identical
  chord list but `oct=` shifted down (or up) by 1-2, often a different
  instrument (e.g. the rhythm guitar doubled by bass, or two guitars an
  octave apart), and usually a lower `vol=` on the doubled layer so it reads
  as weight rather than a second competing lead.
- **A lead/melody line over the rhythm section** (the J-rock intro examples
  layer guitar + bass + drums + a synth countermelody, staggered in with
  `start_times`) is just another track, `melody` role with `notes:` content,
  given a `start=` that lines it up with the section you want it to enter on
  (e.g. `start=8` to enter at bar 8, matching where a prior track's chorus
  begins).
- **Section-specific drum patterns** (a verse groove vs. a busier chorus
  groove, or a fill) don't have to live in one `drums` line's token list
  with `repeat=` -- use **multiple `drums` lines**, each with its own token
  list and a `start=` that places it exactly where that section starts. All
  drum tracks are auto-assigned MIDI channel 9 regardless of how many there
  are, so this works cleanly as long as their bar ranges don't overlap.

The worked Metal example below puts all four of these together (12-bar
verse+chorus, a doubled rhythm guitar, a lead riff entering at the chorus,
and separate verse/chorus drum tracks) and was run through both `validate`
and `compose` end-to-end -- it compiles and renders as one piece, not four
disconnected snippets.

## Rock

Open power-chord rhythm guitar over a driving straight-8th beat.

- Chords track: `instrument: "Overdriven Guitar"` (30) or `"Distortion Guitar"`
  (31, heavier). Chord symbols are **power chords** -- suffix `"5"` (root+fifth,
  2 notes) or `"5(+octave)"` (root+fifth+octave, 3 notes) -- e.g. `"A5"`,
  `"D5"`, `"E5"`. Root movement is usually simple diatonic/fifths motion
  (I-IV-V-IV, or a riff outlining the verse/chorus), not jazz extensions.
- **Power chords always produce a `detected: null` theory-check warning** --
  musicpy's chord-detector can't classify a bare root+fifth dyad as a chord
  family (it needs 3+ notes to pattern-match). This is expected and benign
  for every `"5"`-suffix chord in this doc; don't "fix" it by adding a third
  (that would stop being a power chord).
- Bass track: `"Electric Bass (pick)"` or `"Electric Bass (finger)"`, `style:
  walking` tracks the guitar's roots (walking gracefully degrades to
  root-fifth-root-approach on a 2-note power chord -- no crash, still musical).
- Drums: `"Power Kit"`, straight 8ths, e.g. `K, H, S, H, K, H, S, H` with
  `repeat=` to fill the piece.

```
bpm=138
chords "Overdriven Guitar" name="rhythm guitar" block subdiv=1/8 oct=2: A5 D5 E5 D5
bass "Electric Bass (pick)" name="bass" walking oct=1: A5 D5 E5 D5
drums "Power Kit" name="drums" repeat=4: K, H, S, H, K, H, S, H
```

## Metal

Same power chords as Rock, but the defining move is the **palm-muted chug**:
a single power chord hammered on a fast subdivision instead of one sustained
`block` hit. `block`'s implicit strum only staggers the chord's own tones, it
never repeats the hit across the bar -- to actually repeat the chord, use
`custom_pattern` with an explicit index list the length of your target
subdivision count, e.g. 8 slots for straight 8ths over 1 bar:

- `pattern=[1,2,1,1,2,1,1,2]` with `subdiv=1/8` -- alternates root(1)/fifth(2)
  8 times across the bar. This is *not* tiled by the compiler (unlike
  `arpeggio_*`) -- you must supply the full index sequence for the bar
  yourself.
- For a bigger chug, use `"5(+octave)"` chords (3 tones: root, fifth,
  octave-root) and vary the pattern, e.g. `pattern=[1,1,3,1,1,1,2,1]`.
- Doom metal specifically: very low BPM (25-70), long-duration chords
  (repeat a single segment line's chord fewer times, or just fewer chords
  overall), minimal drums (see the musicpy doc's "doom metal, 25BPM"
  example, which used a slow 4-chord loop with sparse kick/snare).
  `examples/doom-metal-dirge.leadsheet` is a full validated take on this: bpm
  32, four ringing power chords (`E5*2 D5*2 C5*2 B5*2`) an octave apart on
  guitar/bass, and a sparse `K, 0, 0, 0, S, 0, 0, 0` kick/snare pattern. Every
  chord there produces the expected power-chord `detected: null` warning
  described above -- that's correct, not a bug to fix.
- Instrument: `"Distortion Guitar"` for the riff, `"Electric Bass (pick)"`
  for bass (often doubling the guitar's root an octave down).
- Drums: `"Power Kit"` (or `"Standard"`), busier than rock -- add extra kick
  hits, e.g. `K, H, S, H, K, K, S, H`.

This example is a full 12-bar arrangement (8-bar chugging verse, then a
4-bar ringing chorus) demonstrating every technique from "Structuring longer
pieces" above at once: the rhythm guitar doubled an octave down on a second
track, a lead guitar entering only at the chorus (`start=8`), and separate
verse/chorus drum tracks. Ran through both `validate` (clean aside from the
expected power-chord warnings) and `compose` (compiled and rendered audio
successfully) before being included here.

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

## Chiptune / 8-bit / 16-bit / retro game

The classic NES/Game Boy sound comes from `"Lead 1 (square)"` (81) and
`"Lead 2 (sawtooth)"` (82) -- the GM patches closest to a pulse/square-wave
chip synth. Real 8-bit hardware could only play one note per channel at a
time, which is *why* chiptune leans so heavily on fast arpeggios to imply
chords -- that maps directly onto this grammar's `arpeggio_up`/
`arpeggio_updown` styles at a fast subdivision (`subdiv=1/16`), which is
exactly how the source musicpy docs' own "video game 8-bit song style"
example built its chords. Note this is a `melody`-role track using an
ordinary chord-list segment (not `notes:`) -- an arpeggiated lead line is
just a chords-style track.

- Melody/chords: `"Lead 1 (square)"`, `arpeggio_up` (or `arpeggio_updown`
  for a bouncier feel), `subdiv=1/16`.
- Bass: `"Lead 2 (sawtooth)"` or `"Synth Bass 1"`, `root_only` -- simple,
  driving, one note per chord (matches the source material's own bass
  parts, which were plain repeated roots).
- Drums: `"Electronic Kit"`, simple 8th pattern (`K, H, S, H`).
- Keep progressions simple and diatonic (I-vi-IV-V family) -- chiptune reads
  as "retro" through timbre and arpeggiation, not harmonic complexity.

```
bpm=150
melody "Lead 1 (square)" name="lead" arpeggio_up subdiv=1/16 oct=5: C Am F G
bass "Lead 2 (sawtooth)" name="bass" root_only oct=3: C Am F G
drums "Electronic Kit" name="drums" repeat=4: K, H, S, H
```

## Guitar-driven / acoustic

For a solo (or lead) acoustic guitar track, fingerstyle picking reads far
better than a strummed `block`. Use `custom_pattern` on the chords role with
an index list that walks the chord's own tones like a pick would (thumb on
the root, fingers on the higher tones), e.g. `pattern=[1,3,2,3,1,3,2,3]` at
`subdiv=1/8` for a bar of straight 8ths.

- Instrument: `"Acoustic Guitar (steel)"` (26, brighter/folk) or `"Acoustic
  Guitar (nylon)"` (25, warmer/classical).
- Usually no drums, or a very light `"Brush Kit"` if you want a subtle pulse.
- Common progressions: `I-V-vi-IV` (pop-folk), `vi-IV-I-V`, or a simple
  `I-IV-I-V` for a campfire feel.

```
bpm=96
chords "Acoustic Guitar (steel)" name="guitar" custom_pattern pattern=[1,3,2,3,1,3,2,3] subdiv=1/8 oct=3: C G Am F
```

## Pop

Already covered end-to-end by SKILL.md's own "upbeat pop progression" worked
example (`I-V-vi-IV`, block piano chords + walking bass). For variety:
- Swap plain triads for `add9`/`sus2` colors (e.g. `"Cadd9"`, `"Gsus2"`) for a
  more modern pop-folk sound.
- A four-on-the-floor-lite pop-rock beat: `K, H, S, H` on `"Standard"` or
  `"Room Kit"`.

## Lo-fi

Already covered end-to-end by SKILL.md's own worked lo-fi example
(`vi-ii-V-I` on electric piano + root-fifth bass + `notes:` flute melody). For
variety: `"Jazz Kit"` for a softer, brushed drum feel, and 7th/9th chords
throughout (this genre is the one place reaching for `m9`/`maj9` over plain
`m7`/`maj7` reads as *more* correct, not less).

## Reggaeton

Defined by the **dembow** drum pattern, not the chords -- the chords are
usually a simple looping minor-key progression underneath.

- Drums: use the drum token list's `0` token for rests (musicpy's own rest
  token for drum patterns) to place the syncopation. A workable one-bar
  8th-note-grid approximation of "boom-ch-boom-chick":
  `K, 0, K, S2, 0, K, 0, S2` (kick, rest, kick, snare, rest, kick, rest,
  snare) on `instrument: "TR-808 Kit"` (the canonical reggaeton/dembow drum
  machine sound) -- this is a simplified starting point, not a strict
  transcription; nudge the token positions by ear/feel by editing the
  `.leadsheet` file and recomposing.
- Chords: a simple 4-chord minor loop (e.g. `Am-F-C-G` or `Dm-Bb-F-C`),
  `block` at a slow subdiv (`subdiv=1/4`), instrument `"Pad 3 (polysynth)"`
  or a plucked synth feel.
- Bass: `"Synth Bass 1"` or `"Synth Bass 2"`, `root_only` tracking the chord
  roots.
- BPM: 88-96 (reggaeton is usually felt/counted in half-time -- it's often
  described as "176 BPM" double-time in DJ software, but compose at the
  half-time feel here).

```
bpm=92
chords "Pad 3 (polysynth)" name="chords" block subdiv=1/4 oct=4: Am F C G
bass "Synth Bass 1" name="bass" root_only oct=2: Am F C G
drums "TR-808 Kit" name="dembow" repeat=4: K, 0, K, S2, 0, K, 0, S2
```

## EDM

Built on a **four-on-the-floor** kick (a kick on every beat) plus off-beat
open hi-hats, under a sawtooth lead and a sustained pad. There's no
automation/sidechain/filter-sweep in this grammar -- get the "build" feeling
structurally instead: thinner instrumentation (fewer tracks, or `root_only`
bass) for a verse/build section, fuller instrumentation (add the arpeggiated
lead, add the pad's extensions) for the drop, using two tracks with
different `start=` values if you want distinct sections in one piece.

- Drums: `"Electronic Kit"`, kick on every beat + off-beat open hats, e.g.
  `K, H, H, H, K, H, OH, H` (kick on 1 and 3, open hat pickup before 3).
- Pad/chords: `"Pad 3 (polysynth)"`, `block`, reach for `m9`/`maj9`
  extensions for the classic progressive-house pad color.
- Lead: `"Lead 2 (sawtooth)"`, `arpeggio_updown` at `subdiv=1/16` for a
  driving supersaw-like arpeggio.
- Bass: `"Synth Bass 1"`/`"Synth Bass 2"`, `root_only`, locked to the kick.
- Progressions: `vi-IV-I-V` (emotional/progressive) or a static minor-key
  loop (`Am-F-C-G`) are both idiomatic.

```
bpm=128
chords "Pad 3 (polysynth)" name="pad" block subdiv=1/8 oct=4: Am9 Fmaj9 C G
melody "Lead 2 (sawtooth)" name="lead" arpeggio_updown subdiv=1/16 oct=5: Am F C G
bass "Synth Bass 2" name="bass" root_only oct=2: Am F C G
drums "Electronic Kit" name="drums" repeat=4: K, H, H, H, K, H, OH, H
```

## Cinematic / orchestral

The odd genre out here: no fixed drum kit, no signature groove -- the
signature moves are grammar mechanics rather than instrument/pattern picks,
because orchestral writing needs things a 4-8 track pop/rock arrangement
doesn't:

- **Sub-bar harmonic changes.** A chord-list token's default is 1 bar; a
  battle cue's harmonic pushes are often faster than that. Append
  `*<bars>` to any token, e.g. `Cm*0.5` for a chord that lasts half a bar --
  see SKILL.md's B2 grammar reference.
- **Brass/strings that punctuate instead of sustain.** The bare token `r`
  (optionally `r*<bars>`) in a chord-list is a rest -- a stab-and-silence
  brass line is `block: r*3 Cm*1`, not four chords in a row with the
  volume faked down.
- **A motif stated once, reprised later on a different instrument.**
  `define <name> ...` once, then `use: <name> [x<n>]` wherever it recurs --
  a villain motif on solo trumpet, then doubled on strings two minutes
  later, is two `use:` lines, not the motif's note-string retyped twice.
- **More tracks than a pop arrangement needs** (strings split, brass,
  woodwinds, choir, percussion, several motif tracks) -- `MAX_TRACKS` is
  higher than the pop-corpus default suggests; call `list_capabilities` if
  you need the current exact limit.
- **Verifying a track's length wasn't guessed wrong by hand.** `bars=<n>`
  on any track header (except `drums`) hard-errors if its events don't sum
  to exactly `n` bars -- cheap insurance on a `notes:` countermelody that's
  supposed to span the same length as the cue underneath it. Even without
  `bars=`, `validate`/`compose` always report every track's real computed
  length in `track_lengths` -- glance at it before presenting a piece where
  several tracks are meant to line up.

Progressions lean on borrowed/modal color more than pop's diatonic
triads -- minor-key loops with a borrowed bVI/bVII (`Cm-Ab-Eb-Bb`), or a
static pedal under shifting upper-structure chords, both read as
"cinematic" more readily than a plain I-IV-V. See SKILL.md's own "cinematic
cue" worked example for all of the above combined in one short, validated
piece (compiles, renders, zero warnings).

Two more validated pieces cover ground SKILL.md's cinematic-cue example
doesn't:

- `examples/horror-suspense-orchestral.leadsheet` -- eerie/suspenseful
  tension from half-diminished and diminished-seventh harmony
  (`Bm7b5 G7 Cdim7 F#7`) on tremolo strings, a sparse punctuating `Timpani`
  hit on each chord's root (mostly rests via `r*<bars>`, one short stab), and
  a lone `English Horn` line for the "lament" -- the source docs' own "scary
  atmosphere"/"horror ambient" examples' mood, built from this grammar's
  ordinary tools rather than reproduced note-for-note.
- `examples/orchestral-harp-cascade.leadsheet` -- the source docs lean
  heavily on a `%(6451, ...)` chord-tone arpeggiation shorthand (musicpy's
  own digit-sequence syntax) for a distinctive non-linear harp cascade; this
  grammar's nearest equivalent is `custom_pattern` with an explicit
  `pattern=` index list, e.g. `pattern=[1,3,2,4,3,1,4,2]` on `"Orchestral
  Harp"` -- picks chord tones out of strict order instead of a plain
  ascending/descending arpeggio, which is the actual musical effect being
  reached for.

## Ambient / new-age

Sparse and sustained -- the opposite instinct from the driving genres above.
Extended `maj9`/`m9` chords held with `block` at a low `vel=` (50-60), a
`root_only` bass an octave or two below, and a melody that's mostly rests
(a phrase every bar or two, not a continuous line).

- Chords: a pad instrument (`"Pad 1 (new age)"`, `"Pad 2 (warm)"`, or
  `"String Ensemble 2"`), `block`, no `subdiv=` needed (a single held stab).
- Bass: `"Contrabass"` or `"Acoustic Bass"`, `root_only`, low `vel=`.
- Melody: something breathy (`"Flute"`, `"Pan Flute"`, `"Oboe"`), long `dur=`
  values with plenty of `r` tokens between phrases.
- No drums, or something extremely minimal -- this genre reads as "ambient"
  through space and restraint, not rhythm.

```
bpm=78
chords "Pad 1 (new age)" name="pad" block oct=4 vel=55: CM9 Fmaj9 Am9 Gsus
bass "Contrabass" name="bass" root_only oct=1 vel=45: CM9 Fmaj9 Am9 Gsus
melody "Flute" name="air" notes dur=1 vel=60: E5 r C5 r
```

See `examples/ambient-pad-reverie.leadsheet` for the full validated version
of the above.

## Jazz-pop (borrowed/lydian color)

Sits between Pop and Lo-fi: still a clear, singable progression, but colored
with a chord borrowed from outside the plain diatonic set (often the lydian
`#11`-flavored `II7` in a major key) and a slash chord for smoother bass
motion, e.g. `I - II7 - IV - I/3` (`Cmaj7 - D7 - Fmaj7 - Cmaj7/E`).

- Chords: `"Electric Piano 1"`, `block` at `subdiv=1/4` for a gentle comp
  feel.
- Bass: `"Acoustic Bass"`, `walking` -- slash chords like `Cmaj7/E` still
  resolve to a sensible walking line (the bass line follows the chord's
  root, not the slash note).
- Melody: a mallet/keys color (`"Vibraphone"`) works well over jazz
  harmony -- a stepwise `notes:` line outlining the chord tones.

```
bpm=100
chords "Electric Piano 1" name="chords" block subdiv=1/4 oct=3 vel=90: Cmaj7 D7 Fmaj7 Cmaj7/E
bass "Acoustic Bass" name="bass" walking oct=2 vel=85: Cmaj7 D7 Fmaj7 Cmaj7/E
melody "Vibraphone" name="melody" notes dur=1/4 vel=95: G5 F5 E5 F5 E5 D5 E5 D5 C5 B4 G4@1/2
```

See `examples/lydian-jazz-pop.leadsheet` for the full validated version of
the above.

## Structural techniques and extreme tempo

Three more validated pieces in `examples/` exist to show a technique rather
than define a genre:

- `examples/arena-rock-anthem.leadsheet` -- a full verse/chorus arrangement
  in one file: a multi-segment `chords` track (verse `block` at a lower
  register, chorus `block` louder and an octave up), a syncopated bass line
  using `*<bars>` fractions (`Cm*1.5 Bb*0.5 Ab*1 ...`) for the verse and a
  plain `root_fifth` line for the chorus, a lead hook entering only at
  `start=4`, and separate verse/chorus `drums` tracks -- the "Structuring
  longer, multi-section pieces" techniques above, all in one 80s-arena-rock
  package.
- `examples/boss-battle-anthem.leadsheet` -- a `define`/`use` motif combined
  with `section`/`use section`, re-triggered twice at different `start=`
  values (an intro pattern reused as a "phase 2" later in the piece) with a
  melodic hook layered in between -- a compact demonstration of both reuse
  mechanisms working together, distinct from SKILL.md's own `define`/`use`
  and `section` examples (which each show one mechanism in isolation).
- `examples/speedcore-gabber.leadsheet` -- an extreme-tempo (bpm 300)
  four-on-the-floor loop (`K, H, K, H, K, H, K, H` on `"TR-808 Kit"`), kept
  to 2 bars -- the reminder that very high bpm means keeping a track's bar
  count low to stay under the server's `max_duration_seconds` guardrail
  (`list_capabilities` reports the current limit).
