import asyncio
import io
import json
import struct
import wave
from pathlib import Path

from app.core.exceptions import ServiceError


def wav_diagnostics(data):
    """Allowlisted audio metadata only; never expose upstream text/error bodies or audio samples."""
    info = {"payloadType": type(data).__name__}
    if not isinstance(data, bytes):
        return info
    info["byteLength"] = len(data)
    info["format"] = sniff(data) or "unknown"
    if len(data) < 12 or data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        return info
    info["riffDeclaredBytes"] = struct.unpack_from("<I", data, 4)[0]
    offset = 12
    while offset + 8 <= len(data):
        chunk, size = data[offset : offset + 4], struct.unpack_from("<I", data, offset + 4)[0]
        start = offset + 8
        if chunk == b"fmt " and size >= 16 and start + 16 <= len(data):
            tag, channels, rate, _, align, bits = struct.unpack_from("<HHIIHH", data, start)
            info.update(
                formatTag=tag, channels=channels, sampleRate=rate, blockAlign=align, bitsPerSample=bits
            )
        elif chunk == b"data":
            info.update(dataDeclaredBytes=size, dataAvailableBytes=max(0, len(data) - start))
            break
        offset = start + size + size % 2
    try:
        with wave.open(io.BytesIO(data), "rb") as audio:
            expected = audio.getnframes() * audio.getnchannels() * audio.getsampwidth()
            actual = len(audio.readframes(audio.getnframes()))
            info.update(
                expectedFrameBytes=expected, actualFrameBytes=actual, frameDataComplete=expected == actual
            )
    except (wave.Error, EOFError, ValueError, TypeError, struct.error):
        info["stdlibDecoder"] = "unsupported_or_malformed_wav"
    return info


def validate_wav(data, upstream=False):
    try:
        if not isinstance(data, bytes) or len(data) > 10 * 1024 * 1024:
            raise ValueError
        with wave.open(io.BytesIO(data), "rb") as audio:
            if audio.getnframes() < 1 or audio.getframerate() < 1 or audio.getnchannels() not in (1, 2):
                raise ValueError
            expected = audio.getnframes() * audio.getnchannels() * audio.getsampwidth()
            if len(audio.readframes(audio.getnframes())) != expected:
                raise ValueError
    except (wave.Error, EOFError, ValueError, TypeError):
        raise ServiceError(
            "TTS_UNAVAILABLE" if upstream else "UNSUPPORTED_MEDIA",
            "Invalid or incomplete WAV audio.",
            502 if upstream else 415,
        ) from None


def finalize_timbre_wav(data):
    """Finalize the observed Timbre streaming PCM header after the HTTP body is fully received.

    Only the canonical 44-byte, mono 48 kHz/16-bit PCM layout with BOTH size fields
    set to UINT32_MAX is supported. Finite lengths are never repaired; incomplete
    transport reads still fail in the SDK, and frame-aligned EOF cannot prove semantic completeness.
    """
    if isinstance(data, bytes) and 44 <= len(data) <= 10 * 1024 * 1024:
        riff_size = struct.unpack_from("<I", data, 4)[0]
        data_size = struct.unpack_from("<I", data, 40)[0]
        if data[:4] == b"RIFF" and data[8:12] == b"WAVE" and riff_size == data_size == 0xFFFFFFFF:
            fmt_size = struct.unpack_from("<I", data, 16)[0]
            pcm = struct.unpack_from("<HHIIHH", data, 20)
            payload_size = len(data) - 44
            if (
                data[12:16] != b"fmt "
                or fmt_size != 16
                or data[36:40] != b"data"
                or pcm != (1, 1, 48000, 96000, 2, 16)
                or not payload_size
                or payload_size % 2
            ):
                raise ServiceError("TTS_UNAVAILABLE", "Unsupported or incomplete streaming WAV audio.", 502)
            finalized = bytearray(data)
            struct.pack_into("<I", finalized, 4, len(data) - 8)
            struct.pack_into("<I", finalized, 40, payload_size)
            data = bytes(finalized)
    validate_wav(data, upstream=True)
    return data


def sniff(data):
    if data[:4] == b"RIFF" and data[8:12] == b"WAVE":
        return "wav"
    if data[:3] == b"ID3" or data[:2] in (b"\xff\xfb", b"\xff\xf3", b"\xff\xf2"):
        return "mp3"
    return None


async def command(*args):
    try:
        process = await asyncio.create_subprocess_exec(
            *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL
        )
    except FileNotFoundError:
        raise ServiceError("UNCONFIGURED_PROVIDER", "Install ffmpeg and ffprobe for audio uploads.") from None
    try:
        stdout, _ = await asyncio.wait_for(process.communicate(), 20)
    except (TimeoutError, asyncio.CancelledError):
        process.kill()
        await process.wait()
        raise ServiceError("TIMEOUT", "Audio processing timed out.", 504) from None
    if process.returncode:
        raise ServiceError("UNSUPPORTED_MEDIA", "Audio could not be decoded.", 415)
    return stdout


async def prepare_audio(data, directory, settings):
    kind = sniff(data)
    if not kind:
        raise ServiceError("UNSUPPORTED_MEDIA", "Only valid WAV and MP3 uploads are enabled.", 415)
    source = Path(directory) / f"input.{kind}"
    source.write_bytes(data)
    try:
        info = json.loads(
            await command(
                settings.ffprobe_path,
                "-v",
                "error",
                "-protocol_whitelist",
                "file,pipe",
                "-show_entries",
                "format=duration:stream=codec_type",
                "-of",
                "json",
                str(source),
            )
        )
        duration = float(info["format"]["duration"])
        if not 0 < duration <= settings.max_audio_seconds:
            raise ServiceError("INVALID_INPUT", "Audio must be between 0 and 60 seconds.", 422)
        if not any(s.get("codec_type") == "audio" for s in info["streams"]):
            raise ValueError
    except (KeyError, ValueError, TypeError):
        raise ServiceError("UNSUPPORTED_MEDIA", "Audio duration/stream is invalid.", 415) from None
    target = Path(directory) / "normalized.wav"
    # REST v3 accepts WAV without a mandated sample rate. This is an explicit service normalization choice.
    await command(
        settings.ffmpeg_path,
        "-nostdin",
        "-v",
        "error",
        "-protocol_whitelist",
        "file,pipe",
        "-i",
        str(source),
        "-map",
        "0:a:0",
        "-t",
        str(settings.max_audio_seconds),
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-c:a",
        "pcm_s16le",
        "-y",
        str(target),
    )
    validate_wav(target.read_bytes())
    return target, round(duration * 1000)
