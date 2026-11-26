"""Synthesize natural English narration clips using neural edge-tts and FFmpeg."""
import asyncio
import json
import os
import subprocess
import tempfile
import wave
from pathlib import Path

import edge_tts

HERE = Path(__file__).resolve().parent
VOICE = os.environ.get("CANOPY_TTS_VOICE", "en-US-AndrewMultilingualNeural")
RATE = os.environ.get("CANOPY_TTS_RATE", "-2%")


def prep_tts_text(text: str) -> str:
    return (
        text.replace("index.html", "index dot H T M L")
        .replace("PhenoCam", "Pheno Cam")
    )


async def synth_all(segments: list, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="canopy-tts-") as tmp:
        tmp_dir = Path(tmp)
        for key, text in segments:
            mp3_path = tmp_dir / f"{key}.mp3"
            wav_path = out_dir / f"{key}.wav"
            spoken = prep_tts_text(text)
            comm = edge_tts.Communicate(spoken, VOICE, rate=RATE)
            await comm.save(str(mp3_path))
            subprocess.run(
                [
                    "ffmpeg",
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-y",
                    "-i",
                    str(mp3_path),
                    "-af",
                    "silenceremove=start_periods=1:start_silence=0.04:start_threshold=-50dB,"
                    "areverse,"
                    "silenceremove=start_periods=1:start_silence=0.08:start_threshold=-50dB,"
                    "areverse",
                    "-ar",
                    "24000",
                    "-ac",
                    "1",
                    "-c:a",
                    "pcm_s16le",
                    str(wav_path),
                ],
                check=True,
            )


def main() -> None:
    segments = json.loads((HERE / "narration.json").read_text(encoding="utf-8"))
    out_dir = HERE / "audio"
    asyncio.run(synth_all(segments, out_dir))
    total_sec = 0.0
    for key, _ in segments:
        with wave.open(str(out_dir / f"{key}.wav"), "rb") as w:
            dur = w.getnframes() / w.getframerate()
            total_sec += dur
            print(f"  {key:12s}: {dur:5.2f}s")
    print(f"Total speech duration: {total_sec:.2f}s (voice={VOICE}, rate={RATE})")


if __name__ == "__main__":
    main()
