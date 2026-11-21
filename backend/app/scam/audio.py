"""Prepare a voice note or call recording for Azure short-audio speech-to-text.

Azure's short-audio REST API takes 16 kHz mono WAV or Ogg/Opus, at most 60 s. Browsers
record WebM/Opus and phones save M4A/AMR/3GP, so the server converts with ffmpeg when it
is installed (it is in the backend Docker image): mono, 16 kHz, first 55 s only.
Hardening: input from a pipe only (no file or network protocols, so a crafted playlist
cannot make ffmpeg read files or URLs), an allowlist of audio container demuxers, one
thread, at most 2 conversions at once, a time limit, a memory and CPU limit on Linux,
and the output size is capped. Without ffmpeg only WAV and Ogg pass through.
"""
import shutil
import subprocess
import sys
import threading

MAX_SECONDS = 55
FFMPEG_TIMEOUT_SECONDS = 20
MAX_WAV_BYTES = 16000 * 2 * MAX_SECONDS + 4096  # 16-bit mono at 16 kHz
PASS_THROUGH = {"audio/wav": "audio/wav", "audio/x-wav": "audio/wav", "audio/wave": "audio/wav", "audio/ogg": "audio/ogg"}
DEMUXERS = "matroska,webm,ogg,wav,mov,mp4,m4a,3gp,3g2,mj2,mp3,amr,aac"
MAX_PASSTHROUGH_BYTES = 1_000_000  # ~30 s of 16 kHz WAV, the same cap as /speech/stt
MAX_PARALLEL = 2  # conversions at once; others wait (each holds a worker for at most the timeout)
MEMORY_LIMIT_BYTES = 512 * 1024 * 1024
_slots = threading.BoundedSemaphore(MAX_PARALLEL)


def _limit_resources() -> None:  # pragma: no cover - runs in the child process on Linux (the Docker image)
    import resource

    resource.setrlimit(resource.RLIMIT_AS, (MEMORY_LIMIT_BYTES, MEMORY_LIMIT_BYTES))
    resource.setrlimit(resource.RLIMIT_CPU, (FFMPEG_TIMEOUT_SECONDS, FFMPEG_TIMEOUT_SECONDS))


class AudioUnsupported(ValueError):
    """The recording cannot be converted (unknown format, broken file, or no ffmpeg for this format)."""


def ffmpeg_path() -> str | None:
    return shutil.which("ffmpeg")


def _convert(binary: str, data: bytes) -> bytes:
    cmd = [binary, "-hide_banner", "-loglevel", "error", "-nostdin", "-threads", "1", "-protocol_whitelist", "pipe",
           "-format_whitelist", DEMUXERS, "-i", "pipe:0", "-t", str(MAX_SECONDS), "-vn", "-ac", "1", "-ar", "16000",
           "-acodec", "pcm_s16le", "-f", "wav", "pipe:1"]
    limits = _limit_resources if sys.platform != "win32" else None
    if not _slots.acquire(timeout=FFMPEG_TIMEOUT_SECONDS):
        raise AudioUnsupported("server busy converting other recordings")
    try:
        done = subprocess.run(cmd, input=data, capture_output=True, timeout=FFMPEG_TIMEOUT_SECONDS, check=False,  # noqa: S603
                              preexec_fn=limits)  # noqa: PLW1509 - only sets resource limits
    except (subprocess.TimeoutExpired, OSError) as exc:
        raise AudioUnsupported(f"conversion failed: {type(exc).__name__}") from exc
    finally:
        _slots.release()
    if done.returncode != 0 or not done.stdout.startswith(b"RIFF") or len(done.stdout) > MAX_WAV_BYTES:
        raise AudioUnsupported("conversion failed")
    return done.stdout


def prepare_for_stt(data: bytes, content_type: str) -> tuple[bytes, str]:
    """Return (audio bytes, simple content type) ready for speech.recognise."""
    binary = ffmpeg_path()
    if binary:
        return _convert(binary, data), "audio/wav"
    kind = PASS_THROUGH.get(content_type)
    if kind is None:
        raise AudioUnsupported("this recording format needs ffmpeg on the server")
    if len(data) > MAX_PASSTHROUGH_BYTES:
        raise AudioUnsupported("recording too long for speech-to-text without ffmpeg")
    return data, kind
