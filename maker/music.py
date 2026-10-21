"""Gainly background music: a short, quiet track made from code, different for every video.

    python3 gainly_music.py <mood> <seed> <seconds> <out.wav>

mood: calm (savings, FD, PPF), growth (SIP, shares), serious (tax, loans), desi (tanpura and flute, Indian scale).
The seed (for example the video's slug) picks the key, tempo, chords and melody, so every video gets its own track
and the same seed always gives the same track. Everything is synthesised here: no samples, no copyright.
"""
import hashlib
import sys

import numpy as np
from scipy.signal import butter, sosfilt

SR = 44100
rng = np.random.default_rng()


def hz(midi):
    return 440.0 * 2 ** ((midi - 69) / 12)


def env(n, a=0.01, r=0.3, sustain=True):
    """Attack / release envelope over n samples."""
    t = np.arange(n) / SR
    e = np.minimum(1, t / max(a, 1e-4))
    if sustain:
        rel = np.clip((n / SR - t) / max(r, 1e-4), 0, 1)
        return e * rel
    return e * np.exp(-t / max(r, 1e-4))


def lowpass(x, cutoff, order=2):
    return sosfilt(butter(order, cutoff, 'low', fs=SR, output='sos'), x)


def pad(freqs, dur):
    """Soft pad: detuned saws through a low-pass filter, slow attack."""
    n = int(dur * SR)
    t = np.arange(n) / SR
    out = np.zeros(n)
    for f in freqs:
        for d in (-0.12, 0.0, 0.11):
            ph = 2 * np.pi * f * (1 + d / 100) * t + rng.uniform(0, 6.28)
            out += (2 * ((ph / (2 * np.pi)) % 1) - 1)
    out = lowpass(out, 900)
    return out * env(n, a=min(1.2, dur / 3), r=min(1.2, dur / 3)) / (len(freqs) * 3)


def pluck(f, dur, bright=0.5):
    """Karplus-Strong plucked string."""
    n = int(dur * SR)
    period = max(2, int(SR / f))
    buf = rng.uniform(-1, 1, period)
    out = np.zeros(n)
    decay = 0.996 - 0.004 * (1 - bright)
    for i in range(n):
        out[i] = buf[i % period]
        j = (i + 1) % period
        buf[i % period] = decay * 0.5 * (buf[i % period] + buf[j])
    return lowpass(out, 2500 + 3000 * bright) * env(n, a=0.002, r=dur, sustain=False)


def keys(f, dur):
    """Soft electric-piano tone: a few decaying harmonics."""
    n = int(dur * SR)
    t = np.arange(n) / SR
    tone = sum(a * np.sin(2 * np.pi * f * k * t) * np.exp(-t * (1.5 + k)) for k, a in ((1, 1), (2, 0.35), (3, 0.12), (4, 0.05)))
    return tone * env(n, a=0.005, r=0.25)


def flute(f, dur):
    """Bansuri-like: sine with vibrato and a little breath."""
    n = int(dur * SR)
    t = np.arange(n) / SR
    vib = 1 + 0.006 * np.sin(2 * np.pi * 5.2 * t) * np.minimum(1, t / 0.4)
    ph = 2 * np.pi * f * np.cumsum(vib) / SR
    tone = np.sin(ph) + 0.18 * np.sin(2 * ph) + 0.05 * np.sin(3 * ph)
    breath = lowpass(rng.normal(0, 1, n), 3000) * 0.03
    return (tone + breath) * env(n, a=0.08, r=min(0.4, dur / 2))


def tanpura(root, dur):
    """Drone: Pa, Sa, Sa, Sa (low) plucked in a slow loop, rich harmonics."""
    n = int(dur * SR)
    out = np.zeros(n)
    notes = [root - 5, root, root, root - 12]
    step = 0.9
    t0, i = 0.0, 0
    while t0 < dur:
        f = hz(notes[i % 4])
        m = int(min(3.6, dur - t0) * SR)
        tt = np.arange(m) / SR
        s = sum(np.sin(2 * np.pi * f * k * tt * (1 + 0.0004 * k)) / k ** 1.1 for k in range(1, 12))
        s *= np.exp(-tt * 0.8) * np.minimum(1, tt / 0.02)
        a = int(t0 * SR)
        out[a:a + m] += s[: n - a]
        t0 += step
        i += 1
    return lowpass(out, 2200) * 0.12


def kick(dur=0.35):
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = 110 * np.exp(-t * 18) + 45
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 9)


def hat(dur=0.06):
    n = int(dur * SR)
    return sosfilt(butter(2, 7000, 'high', fs=SR, output='sos'), rng.normal(0, 1, n)) * np.exp(-np.arange(n) / SR * 80) * 0.06


def place(track, sound, at):
    a = int(at * SR)
    if a >= len(track):
        return
    b = min(len(track), a + len(sound))
    track[a:b] += sound[: b - a]


MAJOR = [0, 2, 4, 5, 7, 9, 11]
PROGS_MAJOR = [[0, 4, 5, 3], [0, 5, 3, 4], [3, 4, 0, 0], [0, 3, 4, 3], [5, 3, 0, 4]]   # scale degrees (I V vi IV ...)
PROGS_MINOR = [[5, 3, 0, 4], [5, 1, 3, 4], [5, 4, 3, 4]]


def chord(root, degree, octave=0):
    """Triad on a major-scale degree."""
    notes = []
    for k in (0, 2, 4):
        d = degree + k
        notes.append(root + MAJOR[d % 7] + 12 * (d // 7) + 12 * octave)
    return notes


def make(mood, seed, seconds):
    global rng
    s = int(hashlib.sha256(f'{mood}:{seed}'.encode()).hexdigest()[:12], 16)
    rng = np.random.default_rng(s)
    n = int(seconds * SR)
    out = np.zeros(n)
    root = 48 + int(rng.integers(0, 12))   # C3 .. B3

    if mood == 'desi':
        sa = 50 + int(rng.integers(0, 6))   # Sa around D3 .. G3
        out += tanpura(sa, seconds)
        scale = [0, 2, 4, 7, 9, 12, 14]     # Bhupali-like pentatonic (Sa Re Ga Pa Dha)
        t = 1.5
        i = int(rng.integers(0, 3))
        while t < seconds - 2:
            i = int(np.clip(i + rng.choice([-1, 1, 1, 2, -2, 0]), 0, len(scale) - 1))
            d = float(rng.choice([0.5, 0.75, 1.0, 1.5]))
            place(out, flute(hz(sa + 12 + scale[i]), d * 0.95) * 0.22, t)
            t += d + float(rng.choice([0, 0, 0.25, 0.5]))
    else:
        bpm = {'calm': rng.integers(68, 80), 'growth': rng.integers(96, 112), 'serious': rng.integers(82, 92)}[mood]
        beat = 60 / float(bpm)
        bar = 4 * beat
        progs = PROGS_MINOR if mood == 'serious' else PROGS_MAJOR
        prog = progs[int(rng.integers(0, len(progs)))]
        pattern = rng.permutation([0, 1, 2, 1, 2, 0, 1, 2])
        t, b = 0.0, 0
        while t < seconds:
            deg = prog[b % len(prog)]
            c = chord(root, deg)
            place(out, pad([hz(x) for x in c], bar + 0.6) * (0.35 if mood != 'serious' else 0.3), t)
            place(out, keys(hz(root + MAJOR[deg % 7] - 12), bar * 0.9) * 0.25, t)  # bass note
            for k in range(8):                                                    # eighth-note arpeggio
                if mood == 'calm' and k % 2:
                    continue
                note = c[int(pattern[k])] + 12
                if mood == 'serious':
                    place(out, keys(hz(note), beat * 0.9) * 0.18, t + k * beat / 2)
                else:
                    place(out, pluck(hz(note), beat * 1.5, 0.6 if mood == 'growth' else 0.35) * 0.22, t + k * beat / 2)
            if mood == 'growth':
                for k in range(4):
                    place(out, kick() * 0.25, t + k * beat)
                    place(out, hat(), t + k * beat + beat / 2)
            t += bar
            b += 1

    fade = int(1.5 * SR)
    out[:fade] *= np.linspace(0, 1, fade)
    out[-fade:] *= np.linspace(1, 0, fade)
    out *= 0.12 / (np.sqrt(np.mean(out ** 2)) + 1e-9)   # same loudness for every mood
    return np.tanh(out * 1.5) / 1.5 * 0.9                # soft limit, quiet enough to sit under a voice


def write(data, path):
    import wave
    with wave.open(str(path), 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((data * 32767).astype(np.int16).tobytes())


if __name__ == '__main__':
    mood, seed, secs, path = sys.argv[1], sys.argv[2], float(sys.argv[3]), sys.argv[4]
    write(make(mood, seed, secs), path)
    print(path)
