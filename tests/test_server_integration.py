import json

import pytest

from leadsheet import audio, server

requires_fluidsynth = pytest.mark.skipif(
    not audio.audio_available(),
    reason="fluidsynth/ffmpeg not installed in this environment",
)

SAMPLE_B2 = 'bpm=90\nchords "Electric Piano 1" block: Am7 Dm7\n'


def _text_block(blocks):
    return next(b for b in blocks if b.type == "text")


def _write(tmp_path, text, name="piece.leadsheet"):
    path = tmp_path / name
    path.write_text(text)
    return path


@pytest.mark.asyncio
async def test_validate_returns_valid_result(tmp_path):
    path = _write(tmp_path, SAMPLE_B2)
    result = await server.mcp_app.call_tool("validate", {"path": str(path)})
    data = json.loads(_text_block(result).text)
    assert data["valid"] is True
    assert data["errors"] == []
    assert len(data["detected_chords"]) == 2


@pytest.mark.asyncio
async def test_validate_reports_track_lengths(tmp_path):
    path = _write(tmp_path, SAMPLE_B2)
    result = await server.mcp_app.call_tool("validate", {"path": str(path)})
    data = json.loads(_text_block(result).text)
    assert data["track_lengths"] == [{"track": 0, "name": None, "bars": 2.0}]


@pytest.mark.asyncio
async def test_validate_expected_bars_mismatch_is_a_hard_error(tmp_path):
    path = _write(tmp_path, 'bpm=90\nchords "Electric Piano 1" bars=99 block: Am7 Dm7\n')
    result = await server.mcp_app.call_tool("validate", {"path": str(path)})
    data = json.loads(_text_block(result).text)
    assert data["valid"] is False
    assert "expected_bars=99" in data["errors"][0]


@pytest.mark.asyncio
async def test_validate_reports_dsl_syntax_errors(tmp_path):
    path = _write(tmp_path, "not a valid first line\n")
    result = await server.mcp_app.call_tool("validate", {"path": str(path)})
    data = json.loads(_text_block(result).text)
    assert data["valid"] is False
    assert data["errors"]


@pytest.mark.asyncio
async def test_validate_reports_structural_errors(tmp_path):
    path = _write(tmp_path, 'bpm=-1\nchords "Electric Piano 1" block: Zzz9\n')
    result = await server.mcp_app.call_tool("validate", {"path": str(path)})
    data = json.loads(_text_block(result).text)
    assert data["valid"] is False
    assert data["errors"]


@pytest.mark.asyncio
async def test_validate_missing_file(tmp_path):
    result = await server.mcp_app.call_tool("validate", {"path": str(tmp_path / "nope.leadsheet")})
    data = json.loads(_text_block(result).text)
    assert data["valid"] is False
    assert data["errors"]


@requires_fluidsynth
@pytest.mark.asyncio
async def test_compose_saves_tagged_mp3_next_to_source(tmp_path):
    path = _write(tmp_path, 'bpm=90 title="test piece"\nchords "Electric Piano 1" block: Am7 Dm7\n')
    result = await server.mcp_app.call_tool("compose", {"path": str(path)})
    types_seen = {b.type for b in result}
    assert types_seen == {"text"}  # no resource/audio content blocks
    data = json.loads(_text_block(result).text)
    assert data["ok"] is True
    saved = tmp_path / "test-piece.mp3"
    assert data["path"] == str(saved)
    assert saved.exists()
    assert saved.stat().st_size > 0
    assert data["track_lengths"] == [{"track": 0, "name": None, "bars": 2.0}]


@requires_fluidsynth
@pytest.mark.asyncio
async def test_compose_compiles_sub_bar_chords_rests_and_macros(tmp_path):
    """End-to-end proof the three new grammar mechanisms actually compile
    and render, not just parse -- a sub-bar chord, a chord-list rest, and a
    motif defined once and used on two different tracks."""
    text = (
        'bpm=100 title="cinematic snippet"\n'
        'define villain_motif notes dur=1: C4 Eb4 G4\n'
        'chords "Distortion Guitar" block: Am7*0.5 r*0.5 Dm7\n'
        'melody "Trumpet" name="brass" use: villain_motif\n'
        'melody "Violin" name="strings" use: villain_motif x2\n'
    )
    path = _write(tmp_path, text)
    result = await server.mcp_app.call_tool("compose", {"path": str(path)})
    data = json.loads(_text_block(result).text)
    assert data["ok"] is True
    assert (tmp_path / "cinematic-snippet.mp3").exists()


@requires_fluidsynth
@pytest.mark.asyncio
async def test_compose_respects_output_dir_and_collision_suffix(tmp_path):
    path = _write(tmp_path, SAMPLE_B2)
    out_dir = tmp_path / "out"
    result1 = await server.mcp_app.call_tool("compose", {"path": str(path), "output_dir": str(out_dir)})
    data1 = json.loads(_text_block(result1).text)
    assert data1["ok"] is True
    assert data1["path"] == str(out_dir / "untitled.mp3")

    result2 = await server.mcp_app.call_tool("compose", {"path": str(path), "output_dir": str(out_dir)})
    data2 = json.loads(_text_block(result2).text)
    assert data2["ok"] is True
    assert data2["path"] == str(out_dir / "untitled-2.mp3")


@pytest.mark.asyncio
async def test_compose_returns_errors_immediately_without_compiling(tmp_path):
    path = _write(tmp_path, 'bpm=-1\nchords "Electric Piano 1" block: Zzz9\n')
    result = await server.mcp_app.call_tool("compose", {"path": str(path)})
    assert {b.type for b in result} == {"text"}
    data = json.loads(_text_block(result).text)
    assert data["ok"] is False
    assert data["errors"]


@pytest.mark.asyncio
async def test_compose_returns_dsl_syntax_errors_immediately(tmp_path):
    path = _write(tmp_path, "not a valid first line\n")
    result = await server.mcp_app.call_tool("compose", {"path": str(path)})
    data = json.loads(_text_block(result).text)
    assert data["ok"] is False
    assert data["errors"]


@pytest.mark.asyncio
async def test_compose_missing_file(tmp_path):
    result = await server.mcp_app.call_tool("compose", {"path": str(tmp_path / "nope.leadsheet")})
    data = json.loads(_text_block(result).text)
    assert data["ok"] is False
    assert data["errors"]


@pytest.mark.asyncio
async def test_list_capabilities_reflects_musicpy_registries():
    result = await server.mcp_app.call_tool("list_capabilities", {})
    data = json.loads(_text_block(result).text)
    assert len(data["chord_types"]) == 61
    assert len(data["instruments"]) == 128
    assert "Am7" not in data["chord_types"]  # keyed by family name, not chord symbols
    assert data["limits"]["max_tracks"] > 0
