import json

import pytest

from app.core.exceptions import ServiceError
from app.providers.mock_providers import demo_wav
from app.services.audio_utils import prepare_audio


async def test_preprocessing_contract(settings, tmp_path, monkeypatch):
    calls = []

    async def command(*args):
        calls.append(args)
        if args[0] == settings.ffprobe_path:
            return json.dumps({"format": {"duration": "0.5"}, "streams": [{"codec_type": "audio"}]}).encode()
        from pathlib import Path

        Path(args[-1]).write_bytes(demo_wav())
        return b""

    monkeypatch.setattr("app.services.audio_utils.command", command)
    path, duration = await prepare_audio(demo_wav(), tmp_path, settings)
    assert duration == 500 and path.read_bytes() == demo_wav()
    assert calls[0][0] == settings.ffprobe_path and calls[1][0] == settings.ffmpeg_path
    assert "-nostdin" in calls[1] and "file,pipe" in calls[1] and "pcm_s16le" in calls[1]


@pytest.mark.parametrize(
    "info,status",
    [
        ({"format": {"duration": "61"}}, 422),
        ({"format": {"duration": "nan"}}, 422),
        ({"format": {}}, 415),
        ({"format": {"duration": "1"}, "streams": []}, 415),
    ],
)
async def test_bad_probe(settings, tmp_path, monkeypatch, info, status):
    async def command(*args):
        return json.dumps(info).encode()

    monkeypatch.setattr("app.services.audio_utils.command", command)
    with pytest.raises(ServiceError) as error:
        await prepare_audio(demo_wav(), tmp_path, settings)
    assert error.value.status == status
