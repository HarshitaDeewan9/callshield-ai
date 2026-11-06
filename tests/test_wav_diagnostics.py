import struct

from app.providers.mock_providers import demo_wav
from app.services.audio_utils import wav_diagnostics


def test_valid_wav_diagnostics():
    result = wav_diagnostics(demo_wav())
    assert result["format"] == "wav" and result["formatTag"] == 1
    assert result["sampleRate"] == 16000 and result["frameDataComplete"]
    assert result["actualFrameBytes"] == result["expectedFrameBytes"] == 16000


def test_streaming_header_diagnostics():
    data = bytearray(demo_wav())
    struct.pack_into("<I", data, 4, 0xFFFFFFFF)
    struct.pack_into("<I", data, 40, 0xFFFFFFFF)
    result = wav_diagnostics(bytes(data))
    assert result["dataDeclaredBytes"] == 0xFFFFFFFF
    assert result["dataAvailableBytes"] == 16000
    assert not result["frameDataComplete"]


def test_diagnostics_do_not_print_upstream_body():
    assert wav_diagnostics(b'{"error":"private-key-value"}') == {
        "payloadType": "bytes",
        "byteLength": 29,
        "format": "unknown",
    }
