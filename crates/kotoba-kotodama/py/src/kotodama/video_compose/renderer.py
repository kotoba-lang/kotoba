"""Video renderer: scenes + lines → MP4 via PIL compositor + ffmpeg.

Pipeline per line:
  1. (async) TTS → WAV bytes (or silent fallback)
  2. (async) image gen for scene bg (or gradient fallback)
  3. compose_frame → PIL Image
  4. ffmpeg: loop frame + audio WAV → H.264/AAC segment .mp4
  5. ffmpeg concat demuxer → final .mp4

All IO is async; ffmpeg calls are run in a thread pool via asyncio.
"""

from __future__ import annotations

import asyncio
import io
import logging
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from PIL import Image

from .compositor import compose_frame
from .image_client import generate_background
from .tts_client import synthesize

_log = logging.getLogger(__name__)

_VIDEO_W = 1280
_VIDEO_H = 720
_SAMPLE_RATE = 22050
_DEFAULT_LINE_SEC = float(os.environ.get("YUKKURI_LINE_DEFAULT_SEC", "3.0"))


def _run_ffmpeg(args: list[str]) -> None:
    result = subprocess.run(
        ["ffmpeg", "-y"] + args,
        capture_output=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {result.stderr.decode()[-500:]}")


def _write_silent_wav(path: str, duration_sec: float) -> None:
    _run_ffmpeg([
        "-f", "lavfi",
        "-i", f"anullsrc=channel_layout=mono:sample_rate={_SAMPLE_RATE}",
        "-t", str(duration_sec),
        path,
    ])


def _get_audio_duration(wav_bytes: bytes) -> float:
    """Return WAV duration in seconds via ffprobe."""
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        f.write(wav_bytes)
        tmp = f.name
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", tmp],
            capture_output=True, text=True,
        )
        return float(result.stdout.strip() or _DEFAULT_LINE_SEC)
    except Exception:
        return _DEFAULT_LINE_SEC
    finally:
        os.unlink(tmp)


def _frame_and_audio_to_segment(
    frame: Image.Image, wav_bytes: bytes | None, seg_path: str,
    fade_in: bool = False, fade_out: bool = False,
) -> None:
    with tempfile.TemporaryDirectory() as td:
        frame_path = str(Path(td) / "frame.png")
        frame.save(frame_path)
        wav_path = str(Path(td) / "audio.wav")

        if wav_bytes:
            with open(wav_path, "wb") as f:
                f.write(wav_bytes)
            duration = _get_audio_duration(wav_bytes)
        else:
            duration = _DEFAULT_LINE_SEC
            _write_silent_wav(wav_path, duration)

        seg_duration = duration + 0.2
        fade_d = 0.3  # fade duration in seconds

        vf_parts = [f"scale={_VIDEO_W}:{_VIDEO_H}"]
        if fade_in:
            vf_parts.append(f"fade=t=in:st=0:d={fade_d}")
        if fade_out and seg_duration > fade_d:
            vf_parts.append(f"fade=t=out:st={seg_duration - fade_d:.3f}:d={fade_d}")

        _run_ffmpeg([
            "-loop", "1", "-t", str(seg_duration),
            "-i", frame_path,
            "-i", wav_path,
            "-c:v", "libx264",
            "-c:a", "aac",
            "-shortest",
            "-pix_fmt", "yuv420p",
            "-vf", ",".join(vf_parts),
            seg_path,
        ])


def _concat_segments(seg_paths: list[str], out_path: str) -> None:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        for p in seg_paths:
            f.write(f"file '{p}'\n")
        list_path = f.name
    try:
        _run_ffmpeg(["-f", "concat", "-safe", "0", "-i", list_path, "-c", "copy", out_path])
    finally:
        os.unlink(list_path)


async def render_video(
    scenes: list[dict[str, Any]],
    out_path: str,
    tts_url: str = "",
    image_url: str = "",
) -> None:
    """Render a full yukkuri video from scene+line data.

    Args:
        scenes: list of scene dicts, each with:
            - location (str): scene background hint
            - action (str): scene description
            - lines (list[dict]): each with speaker, text, emotion
        out_path: output .mp4 file path
        tts_url: murakumo TTS endpoint (empty = use env var)
        image_url: murakumo image gen endpoint (empty = use env var)
    """
    loop = asyncio.get_event_loop()

    # Pre-collect all (scene, line) pairs so we know which is first/last for fades
    all_lines: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for scene in scenes:
        lines = scene.get("lines") or []
        for line in lines:
            all_lines.append((scene, line))

    total_lines = len(all_lines)

    with tempfile.TemporaryDirectory() as workdir:
        seg_index = 0
        seg_paths: list[str] = []
        # Cache bg image per scene location to avoid redundant API calls
        bg_cache: dict[str, Image.Image | None] = {}

        for idx, (scene, line) in enumerate(all_lines):
            location = scene.get("location", "")
            action = scene.get("action", "")

            # fetch background image once per (location, action) pair
            cache_key = f"{location}|{action}"
            if cache_key not in bg_cache:
                _log.info("scene bg: generating for '%s'", location)
                bg_bytes = await generate_background(location, action, image_url=image_url)
                if bg_bytes:
                    try:
                        bg_cache[cache_key] = Image.open(io.BytesIO(bg_bytes)).convert("RGB")
                    except Exception:
                        bg_cache[cache_key] = None
                else:
                    bg_cache[cache_key] = None
            bg_img = bg_cache[cache_key]

            speaker = line.get("speaker", "left")
            text = line.get("text", "")
            emotion = line.get("emotion", "normal")

            # TTS (async)
            _log.info("  segment %d/%d [%s]: TTS...", idx + 1, total_lines, speaker)
            wav_bytes = await synthesize(text, speaker, tts_url=tts_url)

            # compose frame
            frame = compose_frame(speaker, text, location, emotion, bg_image=bg_img)

            # fade-in on first segment, fade-out on last segment only
            fade_in = idx == 0
            fade_out = idx == total_lines - 1

            # encode segment (CPU-bound, run in thread pool)
            seg_path = str(Path(workdir) / f"seg_{seg_index:04d}.mp4")
            await loop.run_in_executor(
                None, _frame_and_audio_to_segment, frame, wav_bytes, seg_path, fade_in, fade_out
            )
            seg_paths.append(seg_path)
            seg_index += 1
            _log.info("    → segment %s (%d KB)", seg_path, os.path.getsize(seg_path) // 1024)

        if not seg_paths:
            raise ValueError("No segments generated")

        _log.info("Concatenating %d segments → %s", len(seg_paths), out_path)
        await loop.run_in_executor(None, _concat_segments, seg_paths, out_path)

    _log.info("render_video done: %s (%d KB)", out_path, os.path.getsize(out_path) // 1024)
