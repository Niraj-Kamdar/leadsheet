import copy
import json

import pytest

from leadsheet import server

SAMPLE_PIECE = {
    "bpm": 90,
    "tracks": [
        {
            "role": "chords",
            "instrument": "Electric Piano 1",
            "events": [
                {"type": "chord", "chord": "Am7", "bars": 1, "style": "block"},
                {"type": "chord", "chord": "Dm7", "bars": 1, "style": "block"},
            ],
        }
    ],
}


def _text_block(blocks):
    return next(b for b in blocks if b.type == "text")


@pytest.mark.asyncio
async def test_validate_returns_valid_result():
    result = await server.mcp_app.call_tool("validate", {"schema": SAMPLE_PIECE})
    data = json.loads(_text_block(result).text)
    assert data["valid"] is True
    assert data["errors"] == []
    assert len(data["detected_chords"]) == 2


@pytest.mark.asyncio
async def test_validate_reports_structural_errors():
    result = await server.mcp_app.call_tool("validate", {"schema": {"bpm": -1, "tracks": []}})
    data = json.loads(_text_block(result).text)
    assert data["valid"] is False
    assert data["errors"]


@pytest.mark.asyncio
async def test_compose_returns_midi_and_audio_content_blocks():
    result = await server.mcp_app.call_tool("compose", {"schema": SAMPLE_PIECE})
    types_seen = {b.type for b in result}
    assert "text" in types_seen
    assert "resource" in types_seen  # the MIDI blob
    data = json.loads(_text_block(result).text)
    assert "normalized_schema" in data
    assert data["normalized_schema"]["tracks"][0]["events"][0]["chord"] == "Am7"


@pytest.mark.asyncio
async def test_compose_returns_errors_immediately_without_compiling():
    result = await server.mcp_app.call_tool("compose", {"schema": {"bpm": -1, "tracks": []}})
    data = json.loads(_text_block(result).text)
    assert data["valid"] is False
    # no MIDI/audio content blocks -- nothing was compiled or rendered
    assert {b.type for b in result} == {"text"}


@pytest.mark.asyncio
async def test_revise_patches_and_recomposes():
    composed = await server.mcp_app.call_tool("compose", {"schema": SAMPLE_PIECE})
    normalized = json.loads(_text_block(composed).text)["normalized_schema"]

    patched_tracks = copy.deepcopy(normalized["tracks"])
    patched_tracks[0]["events"][0]["chord"] = "Dm9"

    revised = await server.mcp_app.call_tool(
        "revise", {"base_schema": normalized, "patch": {"tracks": patched_tracks}}
    )
    revised_data = json.loads(_text_block(revised).text)
    assert revised_data["normalized_schema"]["tracks"][0]["events"][0]["chord"] == "Dm9"
    # confirm it actually differs from the base
    assert revised_data["normalized_schema"] != normalized


@pytest.mark.asyncio
async def test_list_capabilities_reflects_musicpy_registries():
    result = await server.mcp_app.call_tool("list_capabilities", {})
    data = json.loads(_text_block(result).text)
    assert len(data["chord_types"]) == 61
    assert len(data["instruments"]) == 128
    assert "Am7" not in data["chord_types"]  # keyed by family name, not chord symbols
    assert data["limits"]["max_tracks"] > 0
