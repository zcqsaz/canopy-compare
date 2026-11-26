"""Record the actual offline app in 1080p with neural TTS narration and synced captions."""
import json
import subprocess
import time
import wave
from pathlib import Path
from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent / "project" if (HERE.parent / "project").is_dir() else HERE.parents[1]
segments = json.loads((HERE / "narration.json").read_text(encoding="utf-8"))


def main() -> None:
    (HERE / "frames").mkdir(exist_ok=True)
    audio_dir = HERE / "audio"
    first = wave.open(str(audio_dir / (segments[0][0] + ".wav")))
    rate, channels, width = first.getframerate(), first.getnchannels(), first.getsampwidth()
    first.close()

    audio_bytes = bytearray()
    captions = []

    def silence(seconds: float) -> bytes:
        return bytes(round(seconds * rate) * channels * width)

    def position() -> float:
        return len(audio_bytes) / (channels * width * rate)

    def stamp(seconds: float) -> str:
        total = round(seconds * 1000)
        return f"{total // 3600000:02}:{total // 60000 % 60:02}:{total // 1000 % 60:02},{total % 1000:03}"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--disable-gpu"])
        ctx = browser.new_context(
            viewport={"width": 1728, "height": 972},
            locale="en-GB",
            record_video_dir=HERE / "recording",
            record_video_size={"width": 1728, "height": 972},
        )
        page = ctx.new_page()
        initial = time.monotonic()
        page.goto((PROJECT / "index.html").as_uri())
        page.evaluate("document.fonts.ready")
        page.evaluate(
            """()=>{
                const c = document.createElement('i');
                c.id = 'recording-pointer';
                c.setAttribute('aria-hidden', 'true');
                c.style.cssText = 'position:fixed;top:0;left:0;width:21px;height:21px;border:2.5px solid #b24a26;border-radius:50%;z-index:20000;pointer-events:none;box-shadow:0 0 0 2.5px #ffffffc8;transform:translate(-30px,-30px)';
                document.body.append(c);
                document.addEventListener('mousemove', e => {
                    c.style.transform = `translate(${e.clientX - 10}px, ${e.clientY - 10}px)`;
                });
            }"""
        )

        def point(selector: str) -> None:
            target = page.locator(selector)
            target.scroll_into_view_if_needed()
            rect = target.bounding_box()
            page.mouse.move(
                rect["x"] + 0.50 * rect["width"],
                rect["y"] + 0.50 * rect["height"],
                steps=16,
            )

        def click(selector: str) -> None:
            point(selector)
            page.locator(selector).click()

        def select(selector: str, value: str) -> None:
            point(selector)
            page.select_option(selector, value)

        def top() -> None:
            page.evaluate("window.scrollTo(0, 0)")

        def setdate(value: str) -> None:
            page.locator("#end").fill(value)
            page.locator("#end").dispatch_event("change")

        for key, sentence in segments:
            if key == "settings":
                point("#threshold")
            if key == "spring":
                point(".recommend strong")
            if key == "pictures":
                click("#compare")
                page.locator(".lightbox.pair").wait_for()
            if key == "region":
                page.locator("#show-region").check()
                point(".lightbox figure:first-child .region-note a")
            if key == "mark":
                select("#review-mark", "Colour change visible")
                point("#marked")
            if key == "reveal":
                click("#sheet button")
                click("#reveal")
                page.locator("#outcome").scroll_into_view_if_needed()
                point("#outcome")
            if key == "export":
                top()
                click("#download")
                page.locator("#sheet tbody").wait_for()
            if key == "fall":
                click("#sheet button")
                select("#issue", "2025-10-09")
                select("#channel", "rcc_90")
                point(".recommend strong")
            if key == "fall_reveal":
                click("#reveal")
                page.locator("#outcome").scroll_into_view_if_needed()
                point("#outcome")
            if key == "fall_pair":
                click("#compare")
                point(".lightbox")
            if key == "fallback":
                click("#sheet button")
                top()
                setdate("2025-10-25")
                point("#restore")
            if key == "evidence":
                top()
                click("#view-evidence")
                point(".e-card:nth-child(2) table")
            if key == "model":
                point(".e-card:first-child table")

            start = time.monotonic() - initial
            audio_bytes.extend(silence(max(0.0, start - position())))
            with wave.open(str(audio_dir / (key + ".wav"))) as w:
                audio = w.readframes(w.getnframes())
                duration = w.getnframes() / rate
            begin = position()
            audio_bytes.extend(audio)
            finish = position()

            words = sentence.split()
            number = max(1, round(len(words) / 11))
            bounds = [round(i * len(words) / number) for i in range(number + 1)]
            chunks = [words[a:b] for a, b in zip(bounds, bounds[1:])]
            offset = 0
            for chunk in chunks:
                nxt = offset + len(chunk)
                captions.append(
                    f"{len(captions) + 1}\n"
                    f"{stamp(begin + duration * offset / len(words))} --> "
                    f"{stamp(begin + duration * nxt / len(words))}\n"
                    + " ".join(chunk)
                    + "\n"
                )
                offset = nxt

            page.screenshot(path=HERE / "frames" / (key + ".png"))
            if key == "fallback":
                page.wait_for_timeout(round(duration * 0.62 * 1000))
                click("#restore")
                page.wait_for_timeout(max(50, round((finish - (time.monotonic() - initial)) * 1000)))
            else:
                page.wait_for_timeout(max(50, round((finish - (time.monotonic() - initial)) * 1000)))
            page.wait_for_timeout(400)

        audio_bytes.extend(silence(0.5))
        video = page.video
        ctx.close()
        video.save_as(HERE / "screen.webm")
        browser.close()

    with wave.open(str(HERE / "narration.wav"), "wb") as out:
        out.setnchannels(channels)
        out.setsampwidth(width)
        out.setframerate(rate)
        out.writeframes(audio_bytes)

    (HERE / "canopy-rounds.en.srt").write_text("\n".join(captions), encoding="utf-8")
    filters = (
        "pad=1920:1080:96:0:color=0x19382d,"
        "subtitles=canopy-rounds.en.srt:force_style="
        "'FontName=Arial,FontSize=10,PrimaryColour=&H00F9FFF5,Outline=0,MarginV=10,Alignment=2'"
    )
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            "screen.webm",
            "-i",
            "narration.wav",
            "-vf",
            filters,
            "-r",
            "30",
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "18",
            "-c:a",
            "aac",
            "-b:a",
            "160k",
            "-ar",
            "48000",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            "-shortest",
            "Canopy-Compare-demo.mp4",
        ],
        cwd=HERE,
        check=True,
    )
    print("Finished", round(position(), 2), "seconds")


if __name__ == "__main__":
    main()
