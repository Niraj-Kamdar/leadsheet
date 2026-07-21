# leadsheet

Compose real music with Claude, Codex, or Gemini, without either of you writing a line of
musicpy. `leadsheet` installs a local MCP server (built on
[musicpy](https://github.com/Rainbow-Dreamer/musicpy)) and a client Skill
that together let an AI client turn a chord-symbol-based description of a piece
("Am7-Dm7-G7-Cmaj7 progression, lo-fi piano, 85 BPM") into a real MIDI file
and an audio preview, with a musicology cross-check on every chord.

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
  (`claude mcp add leadsheet -s user`), Codex (`~/.codex/config.toml`), and
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
  small, explicit JSON schema built around chord symbols (`"Am7"`,
  `"G7sus4"`) -- not musicpy's `@`/`%`/`^` operator syntax, and not
  musicpy's own verbose internal JSON.
- **MCP server** (`leadsheet.server`, stdio transport, registered locally):
  exposes four tools --
  - `list_capabilities` -- valid chord types, GM instruments, drum
    kits/tokens, event styles, and guardrail limits, computed live from
    musicpy's own registries.
  - `validate` -- structural + music-theory validation (cross-checks every
    chord against musicpy's own chord-type detector), no compiling.
  - `compose` -- validates, deterministically compiles the schema into a
    musicpy `piece`, renders MIDI + an mp3 preview, returns both inline.
  - `revise` -- applies a small JSON Merge Patch (RFC 7386) to a previous
    composition and recomposes, cheaper than resending the whole piece.

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
