# Genre recipes

Concrete starting points -- instruments, progressions, `style`/`pattern`
tricks, and drum patterns -- for genres that don't fall out obviously from
the general schema guidance in `SKILL.md`. Every full JSON example below was
run through this server's own `validate` and returned `"valid": true` (a
couple of power-chord ones return a specific, expected warning -- explained
under Rock/Metal). Read the relevant section when composing in that genre;
don't try to reconstruct these from memory.

Instrument names/numbers and drum-kit names are quoted verbatim from
`list_capabilities` -- use the string form (e.g. `"Distortion Guitar"`), the
numbers here are just so you recognize them in `list_capabilities` output.

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

## Structuring longer, multi-section pieces

Every genre example below is one short loop -- deliberately, so it's easy to
read. But the musicpy docs' own reference compositions (a J-rock intro, a
full Yui cover, an 8-bit game theme) are all several sections long, with
layered, doubled, and independently-varying parts, not a single 4-bar loop.
Nothing about this schema limits you to a loop -- the same few techniques
those docs pieces use are directly available here:

- **Multi-section arrangements are just a longer `events` list.** A track's
  events concatenate in the order given, so "verse then chorus" is simply
  the verse's chord events followed by the chorus's chord events in the same
  track -- no special section/marker concept needed. Give the chorus louder
  `velocity`, bigger chords (e.g. `"5(+octave)"` instead of `"5"`), or a
  different `style` (e.g. verse `custom_pattern` chug -> chorus ringing
  `block`) so it actually reads as a lift, not just "more of the same chords."
- **Doubling/thickening a riff** (the source docs' doom-metal and
  scary-atmosphere examples both layer the same line an octave apart, e.g.
  musicpy's `a | a - 2`) maps here to a **second track** with the identical
  event list but `octave` shifted down (or up) by 1-2, often a different
  `instrument` (e.g. the rhythm guitar doubled by bass, or two guitars an
  octave apart), and usually a lower `volume` on the doubled layer so it
  reads as weight rather than a second competing lead.
- **A lead/melody line over the rhythm section** (the J-rock intro examples
  layer guitar + bass + drums + a synth countermelody, staggered in with
  `start_times`) is just another track, `role: "melody"` with `RawEvent`
  content, given a `start_bar` that lines it up with the section you want it
  to enter on (e.g. `start_bar: 8` to enter at bar 8, matching where a prior
  track's chorus begins).
- **Section-specific drum patterns** (a verse groove vs. a busier chorus
  groove, or a fill) don't have to live in one `drum_pattern` string with
  `repeat` -- use **multiple `role: "drums"` tracks**, each with its own
  `drum_pattern` and a `start_bar` that places it exactly where that section
  starts. All drum-role tracks are auto-assigned MIDI channel 9 regardless of
  how many there are, so this works cleanly as long as their bar ranges
  don't overlap.

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
  "walking"` tracks the guitar's roots (walking gracefully degrades to
  root-fifth-root-approach on a 2-note power chord -- no crash, still musical).
- Drums: `"Power Kit"`, straight 8ths, e.g. `"K, H, S, H, K, H, S, H"` with
  `repeat` to fill the piece.

```json
{
  "bpm": 138,
  "tracks": [
    {
      "name": "rhythm guitar",
      "role": "chords",
      "instrument": "Overdriven Guitar",
      "events": [
        {"type": "chord", "chord": "A5", "octave": 2, "bars": 1, "style": "block", "subdivision": "1/8"},
        {"type": "chord", "chord": "D5", "octave": 2, "bars": 1, "style": "block", "subdivision": "1/8"},
        {"type": "chord", "chord": "E5", "octave": 2, "bars": 1, "style": "block", "subdivision": "1/8"},
        {"type": "chord", "chord": "D5", "octave": 2, "bars": 1, "style": "block", "subdivision": "1/8"}
      ]
    },
    {
      "name": "bass",
      "role": "bass",
      "instrument": "Electric Bass (pick)",
      "events": [
        {"type": "chord", "chord": "A5", "octave": 1, "bars": 1, "style": "walking"},
        {"type": "chord", "chord": "D5", "octave": 1, "bars": 1, "style": "walking"},
        {"type": "chord", "chord": "E5", "octave": 1, "bars": 1, "style": "walking"},
        {"type": "chord", "chord": "D5", "octave": 1, "bars": 1, "style": "walking"}
      ]
    },
    {
      "name": "drums",
      "role": "drums",
      "instrument": "Power Kit",
      "drum_pattern": "K, H, S, H, K, H, S, H",
      "repeat": 4
    }
  ]
}
```

## Metal

Same power chords as Rock, but the defining move is the **palm-muted chug**:
a single power chord hammered on a fast subdivision instead of one sustained
`block` hit. `block`'s `interval` only staggers the chord's own tones (a
strum), it never repeats the hit across the bar -- to actually repeat the
chord, use `custom_pattern` with an explicit index list the length of your
target subdivision count, e.g. 8 slots for straight 8ths over 1 bar:

- `pattern: [1, 2, 1, 1, 2, 1, 1, 2]` with `subdivision: "1/8"` -- alternates
  root(1)/fifth(2) 8 times across the bar. This is *not* tiled by the
  compiler (unlike `arpeggio_*`) -- you must supply the full index sequence
  for the bar yourself.
- For a bigger chug, use `"5(+octave)"` chords (3 tones: root, fifth,
  octave-root) and vary the pattern, e.g. `[1, 1, 3, 1, 1, 1, 2, 1]`.
- Doom metal specifically: very low BPM (25-70), long `bars` per chord,
  minimal drums (see the musicpy doc's "doom metal, 25BPM" example, which
  used a slow 4-chord loop with sparse kick/snare).
- Instrument: `"Distortion Guitar"` for the riff, `"Electric Bass (pick)"`
  for bass (often doubling the guitar's root an octave down).
- Drums: `"Power Kit"` (or `"Standard"`), busier than rock -- add extra kick
  hits, e.g. `"K, H, S, H, K, K, S, H"`.

This example is a full 12-bar arrangement (8-bar chugging verse, then a
4-bar ringing chorus) demonstrating every technique from "Structuring longer
pieces" above at once: the rhythm guitar doubled an octave down on a second
track, a lead guitar entering only at the chorus (`start_bar: 8`), and
separate verse/chorus drum tracks. Ran through both `validate` (clean aside
from the expected power-chord warnings) and `compose` (compiled and rendered
audio successfully) before being included here.

```json
{
  "bpm": 130,
  "tracks": [
    {
      "name": "rhythm guitar",
      "role": "chords",
      "instrument": "Distortion Guitar",
      "events": [
        {"type": "chord", "chord": "E5", "octave": 2, "bars": 1, "style": "custom_pattern", "pattern": [1, 2, 1, 1, 2, 1, 1, 2], "subdivision": "1/8"},
        {"type": "chord", "chord": "G5", "octave": 2, "bars": 1, "style": "custom_pattern", "pattern": [1, 2, 1, 1, 2, 1, 1, 2], "subdivision": "1/8"},
        {"type": "chord", "chord": "A5", "octave": 2, "bars": 1, "style": "custom_pattern", "pattern": [1, 2, 1, 1, 2, 1, 1, 2], "subdivision": "1/8"},
        {"type": "chord", "chord": "C5", "octave": 2, "bars": 1, "style": "custom_pattern", "pattern": [1, 2, 1, 1, 2, 1, 1, 2], "subdivision": "1/8"},
        {"type": "chord", "chord": "E5", "octave": 2, "bars": 1, "style": "custom_pattern", "pattern": [1, 2, 1, 1, 2, 1, 1, 2], "subdivision": "1/8"},
        {"type": "chord", "chord": "G5", "octave": 2, "bars": 1, "style": "custom_pattern", "pattern": [1, 2, 1, 1, 2, 1, 1, 2], "subdivision": "1/8"},
        {"type": "chord", "chord": "A5", "octave": 2, "bars": 1, "style": "custom_pattern", "pattern": [1, 2, 1, 1, 2, 1, 1, 2], "subdivision": "1/8"},
        {"type": "chord", "chord": "C5", "octave": 2, "bars": 1, "style": "custom_pattern", "pattern": [1, 2, 1, 1, 2, 1, 1, 2], "subdivision": "1/8"},
        {"type": "chord", "chord": "F5(+octave)", "octave": 2, "bars": 1, "style": "block", "subdivision": "1/4"},
        {"type": "chord", "chord": "G5(+octave)", "octave": 2, "bars": 1, "style": "block", "subdivision": "1/4"},
        {"type": "chord", "chord": "C5(+octave)", "octave": 2, "bars": 1, "style": "block", "subdivision": "1/4"},
        {"type": "chord", "chord": "G5(+octave)", "octave": 2, "bars": 1, "style": "block", "subdivision": "1/4"}
      ]
    },
    {
      "name": "rhythm guitar (doubled low)",
      "role": "custom",
      "instrument": "Distortion Guitar",
      "volume": 90,
      "events": [
        {"type": "chord", "chord": "E5", "octave": 1, "bars": 1, "style": "custom_pattern", "pattern": [1, 2, 1, 1, 2, 1, 1, 2], "subdivision": "1/8"},
        {"type": "chord", "chord": "G5", "octave": 1, "bars": 1, "style": "custom_pattern", "pattern": [1, 2, 1, 1, 2, 1, 1, 2], "subdivision": "1/8"},
        {"type": "chord", "chord": "A5", "octave": 1, "bars": 1, "style": "custom_pattern", "pattern": [1, 2, 1, 1, 2, 1, 1, 2], "subdivision": "1/8"},
        {"type": "chord", "chord": "C5", "octave": 1, "bars": 1, "style": "custom_pattern", "pattern": [1, 2, 1, 1, 2, 1, 1, 2], "subdivision": "1/8"},
        {"type": "chord", "chord": "E5", "octave": 1, "bars": 1, "style": "custom_pattern", "pattern": [1, 2, 1, 1, 2, 1, 1, 2], "subdivision": "1/8"},
        {"type": "chord", "chord": "G5", "octave": 1, "bars": 1, "style": "custom_pattern", "pattern": [1, 2, 1, 1, 2, 1, 1, 2], "subdivision": "1/8"},
        {"type": "chord", "chord": "A5", "octave": 1, "bars": 1, "style": "custom_pattern", "pattern": [1, 2, 1, 1, 2, 1, 1, 2], "subdivision": "1/8"},
        {"type": "chord", "chord": "C5", "octave": 1, "bars": 1, "style": "custom_pattern", "pattern": [1, 2, 1, 1, 2, 1, 1, 2], "subdivision": "1/8"},
        {"type": "chord", "chord": "F5(+octave)", "octave": 1, "bars": 1, "style": "block", "subdivision": "1/4"},
        {"type": "chord", "chord": "G5(+octave)", "octave": 1, "bars": 1, "style": "block", "subdivision": "1/4"},
        {"type": "chord", "chord": "C5(+octave)", "octave": 1, "bars": 1, "style": "block", "subdivision": "1/4"},
        {"type": "chord", "chord": "G5(+octave)", "octave": 1, "bars": 1, "style": "block", "subdivision": "1/4"}
      ]
    },
    {
      "name": "lead",
      "role": "melody",
      "instrument": "Electric Guitar (clean)",
      "start_bar": 8,
      "events": [
        {"type": "raw", "notes": "E5[1;1], D5[1;1], C5[1;1], D5[1;1]"}
      ]
    },
    {
      "name": "bass",
      "role": "bass",
      "instrument": "Electric Bass (pick)",
      "events": [
        {"type": "chord", "chord": "E5", "octave": 1, "bars": 1, "style": "root_only"},
        {"type": "chord", "chord": "G5", "octave": 1, "bars": 1, "style": "root_only"},
        {"type": "chord", "chord": "A5", "octave": 1, "bars": 1, "style": "root_only"},
        {"type": "chord", "chord": "C5", "octave": 1, "bars": 1, "style": "root_only"},
        {"type": "chord", "chord": "E5", "octave": 1, "bars": 1, "style": "root_only"},
        {"type": "chord", "chord": "G5", "octave": 1, "bars": 1, "style": "root_only"},
        {"type": "chord", "chord": "A5", "octave": 1, "bars": 1, "style": "root_only"},
        {"type": "chord", "chord": "C5", "octave": 1, "bars": 1, "style": "root_only"},
        {"type": "chord", "chord": "F5", "octave": 1, "bars": 1, "style": "root_only"},
        {"type": "chord", "chord": "G5", "octave": 1, "bars": 1, "style": "root_only"},
        {"type": "chord", "chord": "C5", "octave": 1, "bars": 1, "style": "root_only"},
        {"type": "chord", "chord": "G5", "octave": 1, "bars": 1, "style": "root_only"}
      ]
    },
    {
      "name": "verse drums",
      "role": "drums",
      "instrument": "Power Kit",
      "drum_pattern": "K, H, S, H, K, K, S, H",
      "repeat": 8
    },
    {
      "name": "chorus drums",
      "role": "drums",
      "instrument": "Power Kit",
      "start_bar": 8,
      "drum_pattern": "K, H, S, H, K, H, S, H, K, H, S, H, K, S2, S2, S2",
      "repeat": 2
    }
  ]
}
```

## Chiptune / 8-bit / 16-bit / retro game

The classic NES/Game Boy sound comes from `"Lead 1 (square)"` (81) and
`"Lead 2 (sawtooth)"` (82) -- the GM patches closest to a pulse/square-wave
chip synth. Real 8-bit hardware could only play one note per channel at a
time, which is *why* chiptune leans so heavily on fast arpeggios to imply
chords -- that maps directly onto this schema's `arpeggio_up`/
`arpeggio_updown` styles at a fast subdivision (`"1/16"`), which is exactly
how the source musicpy docs' own "video game 8-bit song style" example
built its chords.

- Melody/chords: `"Lead 1 (square)"`, `style: "arpeggio_up"` (or
  `"arpeggio_updown"` for a bouncier feel), `subdivision: "1/16"`.
- Bass: `"Lead 2 (sawtooth)"` or `"Synth Bass 1"`, `style: "root_only"` --
  simple, driving, one note per chord (matches the source material's own
  bass parts, which were plain repeated roots).
- Drums: `"Electronic Kit"`, simple 8th pattern (`"K, H, S, H"`).
- Keep progressions simple and diatonic (I-vi-IV-V family) -- chiptune reads
  as "retro" through timbre and arpeggiation, not harmonic complexity.

```json
{
  "bpm": 150,
  "tracks": [
    {
      "name": "lead",
      "role": "melody",
      "instrument": "Lead 1 (square)",
      "events": [
        {"type": "chord", "chord": "C", "octave": 5, "bars": 1, "style": "arpeggio_up", "subdivision": "1/16"},
        {"type": "chord", "chord": "Am", "octave": 5, "bars": 1, "style": "arpeggio_up", "subdivision": "1/16"},
        {"type": "chord", "chord": "F", "octave": 5, "bars": 1, "style": "arpeggio_up", "subdivision": "1/16"},
        {"type": "chord", "chord": "G", "octave": 5, "bars": 1, "style": "arpeggio_up", "subdivision": "1/16"}
      ]
    },
    {
      "name": "bass",
      "role": "bass",
      "instrument": "Lead 2 (sawtooth)",
      "events": [
        {"type": "chord", "chord": "C", "octave": 3, "bars": 1, "style": "root_only"},
        {"type": "chord", "chord": "Am", "octave": 3, "bars": 1, "style": "root_only"},
        {"type": "chord", "chord": "F", "octave": 3, "bars": 1, "style": "root_only"},
        {"type": "chord", "chord": "G", "octave": 3, "bars": 1, "style": "root_only"}
      ]
    },
    {
      "name": "drums",
      "role": "drums",
      "instrument": "Electronic Kit",
      "drum_pattern": "K, H, S, H",
      "repeat": 4
    }
  ]
}
```

## Guitar-driven / acoustic

For a solo (or lead) acoustic guitar track, fingerstyle picking reads far
better than a strummed `block`. Use `custom_pattern` on the chords role with
an index list that walks the chord's own tones like a pick would (thumb on
the root, fingers on the higher tones), e.g. `[1, 3, 2, 3, 1, 3, 2, 3]` at
`subdivision: "1/8"` for a bar of straight 8ths.

- Instrument: `"Acoustic Guitar (steel)"` (26, brighter/folk) or `"Acoustic
  Guitar (nylon)"` (25, warmer/classical).
- Usually no drums, or a very light `"Brush Kit"` if you want a subtle pulse.
- Common progressions: `I-V-vi-IV` (pop-folk), `vi-IV-I-V`, or a simple
  `I-IV-I-V` for a campfire feel.

```json
{
  "bpm": 96,
  "tracks": [
    {
      "name": "guitar",
      "role": "chords",
      "instrument": "Acoustic Guitar (steel)",
      "events": [
        {"type": "chord", "chord": "C", "octave": 3, "bars": 1, "style": "custom_pattern", "pattern": [1, 3, 2, 3, 1, 3, 2, 3], "subdivision": "1/8"},
        {"type": "chord", "chord": "G", "octave": 3, "bars": 1, "style": "custom_pattern", "pattern": [1, 3, 2, 3, 1, 3, 2, 3], "subdivision": "1/8"},
        {"type": "chord", "chord": "Am", "octave": 3, "bars": 1, "style": "custom_pattern", "pattern": [1, 3, 2, 3, 1, 3, 2, 3], "subdivision": "1/8"},
        {"type": "chord", "chord": "F", "octave": 3, "bars": 1, "style": "custom_pattern", "pattern": [1, 3, 2, 3, 1, 3, 2, 3], "subdivision": "1/8"}
      ]
    }
  ]
}
```

## Pop

Already covered end-to-end by SKILL.md's own "upbeat pop progression" worked
example (`I-V-vi-IV`, block piano chords + walking bass). For variety:
- Swap plain triads for `add9`/`sus2` colors (e.g. `"Cadd9"`, `"Gsus2"`) for a
  more modern pop-folk sound.
- A four-on-the-floor-lite pop-rock beat: `"K, H, S, H"` on `"Standard"` or
  `"Room Kit"`.

## Lo-fi

Already covered end-to-end by SKILL.md's own worked lo-fi example
(`vi-ii-V-I` on electric piano + root-fifth bass + raw-note-string flute
melody). For variety: `"Jazz Kit"` for a softer, brushed drum feel, and
7th/9th chords throughout (this genre is the one place reaching for
`m9`/`maj9` over plain `m7`/`maj7` reads as *more* correct, not less).

## Reggaeton

Defined by the **dembow** drum pattern, not the chords -- the chords are
usually a simple looping minor-key progression underneath.

- Drums: use `drum_pattern`'s `"0"` token for rests (musicpy's own rest
  token for drum patterns) to place the syncopation. A workable one-bar
  8th-note-grid approximation of "boom-ch-boom-chick":
  `"K, 0, K, S2, 0, K, 0, S2"` (kick, rest, kick, snare, rest, kick, rest,
  snare) on `instrument: "TR-808 Kit"` (the canonical reggaeton/dembow drum
  machine sound) -- this is a simplified starting point, not a strict
  transcription; nudge the token positions by ear/feel via `revise`.
- Chords: a simple 4-chord minor loop (e.g. `Am-F-C-G` or `Dm-Bb-F-C`),
  `style: "block"` at a slow subdivision (`"1/4"`), instrument `"Pad 3
  (polysynth)"` or a plucked synth feel.
- Bass: `"Synth Bass 1"` or `"Synth Bass 2"`, `style: "root_only"` tracking
  the chord roots.
- BPM: 88-96 (reggaeton is usually felt/counted in half-time -- it's often
  described as "176 BPM" double-time in DJ software, but compose at the
  half-time feel here).

```json
{
  "bpm": 92,
  "tracks": [
    {
      "name": "chords",
      "role": "chords",
      "instrument": "Pad 3 (polysynth)",
      "events": [
        {"type": "chord", "chord": "Am", "octave": 4, "bars": 1, "style": "block", "subdivision": "1/4"},
        {"type": "chord", "chord": "F", "octave": 4, "bars": 1, "style": "block", "subdivision": "1/4"},
        {"type": "chord", "chord": "C", "octave": 4, "bars": 1, "style": "block", "subdivision": "1/4"},
        {"type": "chord", "chord": "G", "octave": 4, "bars": 1, "style": "block", "subdivision": "1/4"}
      ]
    },
    {
      "name": "bass",
      "role": "bass",
      "instrument": "Synth Bass 1",
      "events": [
        {"type": "chord", "chord": "Am", "octave": 2, "bars": 1, "style": "root_only"},
        {"type": "chord", "chord": "F", "octave": 2, "bars": 1, "style": "root_only"},
        {"type": "chord", "chord": "C", "octave": 2, "bars": 1, "style": "root_only"},
        {"type": "chord", "chord": "G", "octave": 2, "bars": 1, "style": "root_only"}
      ]
    },
    {
      "name": "dembow",
      "role": "drums",
      "instrument": "TR-808 Kit",
      "drum_pattern": "K, 0, K, S2, 0, K, 0, S2",
      "repeat": 4
    }
  ]
}
```

## EDM

Built on a **four-on-the-floor** kick (a kick on every beat) plus off-beat
open hi-hats, under a sawtooth lead and a sustained pad. There's no
automation/sidechain/filter-sweep in this schema -- get the "build" feeling
structurally instead: thinner instrumentation (fewer tracks, or `root_only`
bass) for a verse/build section, fuller instrumentation (add the arpeggiated
lead, add the pad's extensions) for the drop, using two tracks with
different `start_bar`s if you want distinct sections in one piece.

- Drums: `"Electronic Kit"`, kick on every beat + off-beat open hats, e.g.
  `"K, H, H, H, K, H, OH, H"` (kick on 1 and 3, open hat pickup before 3).
- Pad/chords: `"Pad 3 (polysynth)"`, `style: "block"`, reach for `m9`/`maj9`
  extensions for the classic progressive-house pad color.
- Lead: `"Lead 2 (sawtooth)"`, `style: "arpeggio_updown"` at `"1/16"` for a
  driving supersaw-like arpeggio.
- Bass: `"Synth Bass 1"`/`"Synth Bass 2"`, `style: "root_only"`, locked to
  the kick.
- Progressions: `vi-IV-I-V` (emotional/progressive) or a static minor-key
  loop (`Am-F-C-G`) are both idiomatic.

```json
{
  "bpm": 128,
  "tracks": [
    {
      "name": "pad",
      "role": "chords",
      "instrument": "Pad 3 (polysynth)",
      "events": [
        {"type": "chord", "chord": "Am9", "octave": 4, "bars": 1, "style": "block", "subdivision": "1/8"},
        {"type": "chord", "chord": "Fmaj9", "octave": 4, "bars": 1, "style": "block", "subdivision": "1/8"},
        {"type": "chord", "chord": "C", "octave": 4, "bars": 1, "style": "block", "subdivision": "1/8"},
        {"type": "chord", "chord": "G", "octave": 4, "bars": 1, "style": "block", "subdivision": "1/8"}
      ]
    },
    {
      "name": "lead",
      "role": "melody",
      "instrument": "Lead 2 (sawtooth)",
      "events": [
        {"type": "chord", "chord": "Am", "octave": 5, "bars": 1, "style": "arpeggio_updown", "subdivision": "1/16"},
        {"type": "chord", "chord": "F", "octave": 5, "bars": 1, "style": "arpeggio_updown", "subdivision": "1/16"},
        {"type": "chord", "chord": "C", "octave": 5, "bars": 1, "style": "arpeggio_updown", "subdivision": "1/16"},
        {"type": "chord", "chord": "G", "octave": 5, "bars": 1, "style": "arpeggio_updown", "subdivision": "1/16"}
      ]
    },
    {
      "name": "bass",
      "role": "bass",
      "instrument": "Synth Bass 2",
      "events": [
        {"type": "chord", "chord": "Am", "octave": 2, "bars": 1, "style": "root_only"},
        {"type": "chord", "chord": "F", "octave": 2, "bars": 1, "style": "root_only"},
        {"type": "chord", "chord": "C", "octave": 2, "bars": 1, "style": "root_only"},
        {"type": "chord", "chord": "G", "octave": 2, "bars": 1, "style": "root_only"}
      ]
    },
    {
      "name": "drums",
      "role": "drums",
      "instrument": "Electronic Kit",
      "drum_pattern": "K, H, H, H, K, H, OH, H",
      "repeat": 4
    }
  ]
}
```
