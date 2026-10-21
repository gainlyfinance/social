"""Makes the picture post and the vertical video for each queue item.

    python3 maker/make.py queue/samples.json out/            all items
    python3 maker/make.py queue/samples.json out/ <slug>     one item

For each item: out/<slug>.jpg (1080x1350 feed picture) and out/<slug>.mp4 (1080x1920, 25 fps, H.264 + AAC, with our
own background music).

Voice: when GOOGLE_TTS_KEY and VOICE (a Google voice name such as hi-IN-Chirp3-HD-Kore) are set and the item has
"voice_lines" (one sentence per scene), every scene is read aloud, each scene lasts as long as its sentence needs,
and the music is lowered under the voice.
"""
import json
import pathlib
import subprocess
import sys
import tempfile

from playwright.sync_api import sync_playwright

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import music  # noqa: E402
import voice as tts  # noqa: E402
import numpy as np  # noqa: E402
import os  # noqa: E402

FPS = 25


def card(page, item, out):
    page.set_viewport_size({'width': 1080, 'height': 1350})
    page.add_init_script(f'window.ITEM = {json.dumps(item, ensure_ascii=False)}; window.MODE = "card";')
    page.goto((HERE / 'template.html').as_uri())
    page.evaluate('window.READY')
    page.screenshot(path=str(out), type='jpeg', quality=92)


SCENES = ['s1', 's2', 's3', 's4', 's5', 's6']
BASE = [3.4, 4.8, 6.6, 5.4, 4.6, 4.7]   # seconds per scene without voice
OVERLAP = 0.2                           # scenes cross-fade
LEAD = 0.35                             # voice starts this long after its scene


def voice_track(item, voice_name):
    """Reads each scene's line. Returns (timings for the page, voice samples) or (None, None) without voice."""
    lines = item.get('voice_lines')
    if not lines or not voice_name or not os.environ.get('GOOGLE_TTS_KEY'):
        return None, None
    clips = [tts.speak(t, voice_name) for t in lines]
    timings, start = {}, 0.0
    for sid, base, clip in zip(SCENES, BASE, clips):
        dur = max(base, len(clip) / tts.SR + LEAD + 0.6)
        timings[sid] = [round(start, 3), round(start + dur, 3)]
        start += dur - OVERLAP
    total = timings['s6'][1]
    track = np.zeros(int((total + 0.5) * tts.SR), np.float32)
    for sid, clip in zip(SCENES, clips):
        a = int((timings[sid][0] + LEAD) * tts.SR)
        track[a:a + len(clip)] += clip[: len(track) - a]
    track *= 0.9 / (np.max(np.abs(track)) + 1e-9)
    return timings, track


def video(page, item, out, voice_name=None):
    timings, track = voice_track(item, voice_name)
    page.set_viewport_size({'width': 1080, 'height': 1920})
    page.add_init_script(f'window.ITEM = {json.dumps(item, ensure_ascii=False)}; window.MODE = "video";'
                         + (f' window.TIMINGS = {json.dumps(timings)};' if timings else ''))
    page.goto((HERE / 'template.html').as_uri())
    page.evaluate('window.READY')
    duration = page.evaluate('window.DURATION')
    frames = int(duration * FPS)

    with tempfile.TemporaryDirectory() as tmp:
        silent = pathlib.Path(tmp) / 'video.mp4'
        enc = subprocess.Popen(['ffmpeg', '-loglevel', 'error', '-y', '-f', 'image2pipe', '-framerate', str(FPS), '-c:v', 'mjpeg',
                                '-i', '-', '-c:v', 'libx264', '-preset', 'medium', '-crf', '20', '-pix_fmt', 'yuv420p',
                                '-movflags', '+faststart', str(silent)], stdin=subprocess.PIPE)
        for f in range(frames):
            page.evaluate(f'renderAt({f / FPS})')
            enc.stdin.write(page.screenshot(type='jpeg', quality=90))
        enc.stdin.close()
        if enc.wait() != 0:
            raise SystemExit('ffmpeg failed while encoding frames')

        wav = pathlib.Path(tmp) / 'music.wav'
        music.write(music.make(item.get('mood', 'calm'), item['slug'], duration + 0.5), wav)
        voice = None
        if track is not None:
            voice = str(pathlib.Path(tmp) / 'voice.wav')
            music.write(track, voice)
        if voice:
            # Voice on top, music ducked to about a fifth under it.
            audio = ['-i', str(wav), '-i', voice, '-filter_complex',
                     '[2:a]volume=1.0[v];[1:a]volume=0.22[m];[m][v]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[a]', '-map', '0:v', '-map', '[a]']
            cmd = ['ffmpeg', '-loglevel', 'error', '-y', '-i', str(silent)] + audio
        else:
            cmd = ['ffmpeg', '-loglevel', 'error', '-y', '-i', str(silent), '-i', str(wav), '-map', '0:v', '-map', '1:a', '-filter:a', 'volume=0.8']
        cmd += ['-c:v', 'copy', '-c:a', 'aac', '-b:a', '160k', '-shortest', '-movflags', '+faststart', str(out)]
        subprocess.run(cmd, check=True)


def main():
    queue = json.loads(pathlib.Path(sys.argv[1]).read_text())
    out = pathlib.Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    only = sys.argv[3] if len(sys.argv) > 3 else None
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for item in queue:
            if only and item['slug'] != only:
                continue
            page = browser.new_page()
            card(page, item, out / f"{item['slug']}.jpg")
            page.close()
            voice_name = os.environ.get('VOICE')
            page = browser.new_page()
            suffix = f"-{voice_name}" if voice_name and os.environ.get('VOICE_IN_NAME') else ''
            video(page, item, out / f"{item['slug']}{suffix}.mp4", voice_name)
            page.close()
            print(item['slug'])
        browser.close()


if __name__ == '__main__':
    main()
