import pytest

from leadsheet import audio, render

requires_mp3 = pytest.mark.skipif(
    not audio.mp3_available(),
    reason="fluidsynth/ffmpeg not installed in this environment",
)

SAMPLE_B2 = 'bpm=90\nchords "Electric Piano 1" block: Am7 Dm7\n'


def test_dsl_syntax_error_is_reported_as_invalid():
    result = render.render_piece("not a valid first line\n")
    assert result.dsl_valid is False
    assert result.errors


def test_theory_check_failure_is_reported_as_invalid():
    result = render.render_piece('bpm=-1\nchords "Electric Piano 1" block: Zzz9\n')
    assert result.dsl_valid is False
    assert result.errors


def test_duration_seconds_matches_hand_computed_bpm_bars_math():
    result = render.render_piece(SAMPLE_B2, formats=())
    assert result.dsl_valid is True
    # 2 bars total (Am7 + Dm7, one bar each) at 90 bpm: 2 * 4 * 60 / 90
    assert result.duration_seconds == pytest.approx(2 * 4 * 60 / 90)


def test_container_mode_formats_reports_render_ok_false_with_no_fallback(monkeypatch):
    monkeypatch.setattr(audio, "fluidsynth_available", lambda: False)
    monkeypatch.setattr(audio, "ffmpeg_available", lambda: False)
    monkeypatch.setattr(audio, "tinysoundfont_available", lambda: False)

    result = render.render_piece(SAMPLE_B2, formats=("mp3",))

    assert result.dsl_valid is True
    assert result.render_ok is False
    assert result.audio_bytes is None
    assert result.audio_format is None


@requires_mp3
def test_default_formats_path_renders_tagged_mp3():
    result = render.render_piece(SAMPLE_B2)
    assert result.dsl_valid is True
    assert result.render_ok is True
    assert result.audio_format == "mp3"
    assert result.audio_backend == "fluidsynth+ffmpeg"
    assert result.audio_bytes
    assert result.track_lengths == [{"track": 0, "name": None, "bars": 2.0}]


def test_default_formats_falls_back_to_midi_only_when_no_renderer(monkeypatch):
    monkeypatch.setattr(audio, "fluidsynth_available", lambda: False)
    monkeypatch.setattr(audio, "ffmpeg_available", lambda: False)
    monkeypatch.setattr(audio, "tinysoundfont_available", lambda: False)

    result = render.render_piece(SAMPLE_B2)

    assert result.dsl_valid is True
    assert result.render_ok is True
    assert result.audio_bytes is None
    assert result.audio_format is None
    assert result.midi_bytes
