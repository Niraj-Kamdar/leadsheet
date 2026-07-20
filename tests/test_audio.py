import pytest
import musicpy as mp

from leadsheet import audio
from leadsheet.compiler import compile_piece
from leadsheet.schema import PieceSchema

requires_fluidsynth = pytest.mark.skipif(
    not audio.audio_available(),
    reason="fluidsynth/ffmpeg not installed in this environment",
)


def _sample_midi_bytes() -> bytes:
    schema = PieceSchema(
        bpm=90,
        tracks=[
            {
                "role": "chords",
                "instrument": "Electric Piano 1",
                "events": [{"type": "chord", "chord": "Am7", "bars": 1, "style": "block"}],
            }
        ],
    )
    piece_obj = compile_piece(schema)
    return mp.write(piece_obj, bpm=schema.bpm, save_as_file=False).getvalue()


def test_audio_unavailable_when_binaries_missing(monkeypatch):
    monkeypatch.setattr(audio, "fluidsynth_available", lambda: False)
    with pytest.raises(audio.AudioUnavailable):
        audio.render_mp3(_sample_midi_bytes())


@requires_fluidsynth
def test_render_mp3_produces_valid_non_empty_mp3():
    mp3_bytes = audio.render_mp3(_sample_midi_bytes())
    assert len(mp3_bytes) > 0
    # sniff the header rather than just checking non-empty: either a
    # legitimate ID3v2 tag or an MPEG frame sync (0xFFE.. / 0xFFF..)
    is_id3 = mp3_bytes[:3] == b"ID3"
    is_mpeg_frame_sync = mp3_bytes[0] == 0xFF and (mp3_bytes[1] & 0xE0) == 0xE0
    assert is_id3 or is_mpeg_frame_sync
