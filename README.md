# leadsheet

Compose simple, playable music with ChatGPT, Claude, Codex, or Gemini — without a
DAW, a subscription to a music-generation service, or specialist music software.
`leadsheet` installs a local MCP server and client Skill that turn a natural language 
prompt into a compact, editable `.leadsheet` file, then validate and render
it as a tagged MP3.

Version 0.2.0 introduces the `.leadsheet` format. It is a plain-text, line-oriented
music DSL designed for both AI generation and human editing: it is diffable,
version-controllable, and substantially cheaper to send through an LLM than verbose
JSON or code-based music notation.

## Install

```bash
uv tool install leadsheet   # recommended
leadsheet setup
```

or, without `uv`:

```bash
pip install leadsheet
leadsheet setup
```

`leadsheet setup` is a required, one-time follow-up step -- pip/wheel
installs have no reliable post-install hook, so this is what actually:

- registers the MCP server with every detected client: Claude Code globally
  (`claude mcp add leadsheet -s user`), Codex (`~/.codex/config.toml`), or
  Gemini (`~/.gemini/settings.json`)
- installs the Skill for each detected client: `~/.claude/skills/leadsheet/`
  for Claude Code and `~/.agents/skills/leadsheet/` for Codex
- checks for `fluidsynth` (needed for the audio preview -- MIDI output
  works either way) and prints an install hint if it's missing
- downloads and caches a General MIDI soundfont for rendering

`uv tool install` is preferred because it keeps `leadsheet` in a stable,
persistent, isolated environment outside any project venv -- `claude mcp
add` stores an **absolute path** to the Python interpreter that must keep
working long after this install command finishes, so it shouldn't live in
a venv you might later delete.

Re-run `leadsheet setup` any time after upgrading (`pip install -U
leadsheet` / `uv tool upgrade leadsheet`) to refresh the registered server
and the installed skill.

After setup, restart your configured client and ask it to compose something.

### AI client support

The server uses the standard MCP protocol over local stdio, so the same
`.leadsheet` workflow works with MCP-enabled clients:

| Client | Setup |
| --- | --- |
| ChatGPT | Add a local MCP server using command `python -m leadsheet.server` and the Python interpreter from the `leadsheet` installation. |
| Claude Code | Run `leadsheet setup`; it registers the server and installs the Skill. |
| Codex | Ensure `~/.codex/config.toml` exists, then run `leadsheet setup`. |
| Gemini CLI | Ensure `~/.gemini/settings.json` exists, then run `leadsheet setup`. |

For ChatGPT, configure the server in the MCP/developer settings of the ChatGPT
client you use; the command must point at the same environment where
`leadsheet` was installed. After connecting, ask ChatGPT or Gemini to create a
`.leadsheet` file, call `validate`, and then call `compose`.

## The `.leadsheet` format

A file starts with a required tempo line, followed by chord, bass, melody, drum,
or custom tracks. The format keeps musical intent visible while factoring out
repeated values:

```text
bpm=85 title="Night Drive" key="A minor"

chords "Electric Piano 1" block subdiv=1: Am7 Fmaj7 C G
bass "Electric Bass (finger)" root_fifth oct=2: Am7 Fmaj7 C G
melody "Flute" notes dur=1/4: A4 C5 E5 x2 r E5 C5 A4
drums "Standard" repeat=8: K,H,S,H
```

Melody is native to the DSL, with a compact notation designed for both AI and
human authors. Useful note forms include:

- `dur=`, `int=`, and `vel=` set segment defaults.
- `E5@1/2` overrides one note's duration; `r` is a rest.
- `C5+E5+G5` plays a simultaneous-note stack.
- `E5 x8` repeats the preceding note, rest, or stack.

### Reuse and song structure

Define reusable content once and apply it to multiple tracks. `transpose=` and
`vel=` are call-site overrides:

```text
define hook notes dur=1/4: E5 G5 A5 x2 G5 E5

melody "Flute" use: hook
melody "Violin" use: hook transpose=-3 vel=70
```

For a chorus or other multi-track passage, define a section and place it at any
bar offset:

```text
section chorus:
  chords "Electric Piano 1" block: Fmaj7 C G Am
  bass "Acoustic Bass" root_fifth oct=2: Fmaj7 C G Am
  drums "Standard" repeat=4: K,H,S,H
  melody "Flute" notes dur=1/4: F5 A5 C5 x2 A5 F5

use section chorus start=8
use section chorus start=24
```

The full grammar and constraints are in the installed Skill at
`src/leadsheet/skill/SKILL.md`. The `examples/` directory contains complete,
validated `.leadsheet` files.

## Compose from a `.leadsheet` file

AI clients normally create and edit the file through the MCP tools. From the
command line, the same local server can be started with:

```bash
python -m leadsheet.server
```

The MCP tools are:

- `list_capabilities` — available chord types, GM instruments, drum kits, styles,
  and guardrails.
- `validate` — parses and theory-checks a `.leadsheet` file without rendering.
- `compose` — validates, compiles, renders, and saves the tagged MP3.

After a change, edit the same `.leadsheet` file and compose it again. The text
file is the source of truth.

### Audio previews (optional but recommended)

Audio rendering needs the `fluidsynth` binary on `PATH`:

```bash
brew install fluidsynth       # macOS
apt-get install fluidsynth    # Debian/Ubuntu
```

Without it, `leadsheet` still returns a fully valid MIDI file for every
composition -- you just won't get an inline audio preview until
fluidsynth is installed and `leadsheet setup` is re-run.

## Other commands

```bash
leadsheet status      # what's currently configured
leadsheet uninstall    # remove the MCP registration and skill
leadsheet uninstall --purge-cache   # also delete the cached soundfont
```

## How it works

- **Skill** (`~/.claude/skills/leadsheet/SKILL.md` or
  `~/.agents/skills/leadsheet/SKILL.md`): teaches the client a
  small, explicit schema built around chord symbols (`"Am7"`,
  `"G7sus4"`) and the `.leadsheet` text format.
- **MCP server** (`leadsheet.server`, stdio transport, registered locally):
  exposes four tools --
  - `list_capabilities` -- valid chord types, GM instruments, drum
    kits/tokens, event styles, and guardrail limits.
  - `validate` -- structural and music-theory validation, without compiling.
  - `compose` -- validates, compiles, renders, and returns an mp3 preview.

Everything is local and stateless: no database, no server-side file
storage, no network calls except the one-time soundfont download.

## Roadmap

v1 (this) is entirely local. A planned v1.1 hosts the same MCP server on
Cloudflare and records input/output pairs to disk or an S3-like store (no
database) purely so they can be used as future fine-tuning data -- not
built yet.

## Development

```bash
uv sync
uv run pytest
```

Audio-pipeline tests that need `fluidsynth` are skipped automatically if
it isn't installed in the dev environment.

## License

AGPL-3.0-or-later -- see [LICENSE](LICENSE).
