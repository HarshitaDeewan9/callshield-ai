import io
import struct
import wave

import pytest

from app.core.exceptions import ServiceError
from app.providers.gnani_timbre import GnaniTimbreProvider
from app.services.audio_utils import finalize_timbre_wav, validate_wav


def pcm_wav(size=983040):
    output = io.BytesIO()
    with wave.open(output, "wb") as audio:
        audio.setparams((1, 2, 48000, 0, "NONE", ""))
        audio.writeframes(b"\0" * size)
    return output.getvalue()


def streaming_wav():
    data = bytearray(pcm_wav())
    struct.pack_into("<I", data, 4, 0xFFFFFFFF)
    struct.pack_into("<I", data, 40, 0xFFFFFFFF)
    return bytes(data)


def test_observed_timbre_header_is_finalized_without_changing_audio():
    original = streaming_wav()
    result = finalize_timbre_wav(original)
    assert len(result) == 983084
    assert result[44:] == original[44:]
    assert struct.unpack_from("<I", result, 4)[0] == len(result) - 8
    assert struct.unpack_from("<I", result, 40)[0] == 983040
    validate_wav(result, upstream=True)
    with wave.open(io.BytesIO(result), "rb") as audio:
        assert audio.getnframes() == 491520
        assert audio.getframerate() == 48000


def test_regular_wav_is_unchanged():
    original = pcm_wav(100)
    assert finalize_timbre_wav(original) is original


@pytest.mark.parametrize(
    "data",
    [pcm_wav()[:-2], streaming_wav()[:-1], streaming_wav()[:44], b"error response", b"RIFF", b""],
    ids=["finite-truncated", "partial-frame", "no-samples", "non-audio", "short-header", "empty"],
)
def test_truncated_and_invalid_audio_still_fails(data):
    with pytest.raises(ServiceError, match="TTS_UNAVAILABLE"):
        finalize_timbre_wav(data)


@pytest.mark.parametrize(
    "offset,value", [(16, 18), (20, 3), (22, 2), (24, 16000), (28, 1234), (32, 4), (34, 24)]
)
def test_unexpected_streaming_format_is_not_guessed(offset, value):
    data = bytearray(streaming_wav())
    struct.pack_into("<I" if offset in (16, 24, 28) else "<H", data, offset, value)
    with pytest.raises(ServiceError, match="TTS_UNAVAILABLE"):
        finalize_timbre_wav(bytes(data))


def test_uploaded_streaming_wav_remains_strict():
    with pytest.raises(ServiceError, match="UNSUPPORTED_MEDIA"):
        validate_wav(streaming_wav())


async def test_provider_returns_finalized_wav(settings):
    class Client:
        def synthesize(self, *args, **kwargs):
            return streaming_wav()

    audio = await GnaniTimbreProvider(settings, client=Client()).synthesize("Warning", "en-IN", "Kaveri")
    assert audio.mime == "audio/wav" and not audio.mock
    assert audio.data == pcm_wav()
