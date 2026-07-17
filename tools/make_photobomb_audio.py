#!/usr/bin/env python3
"""Render audio_files/photobomb-countdown.mp3 — the Photo Bomb camera sequence.

Timeline comes from effects/photobomb_shot.py (single source of truth shared
with the lighting effect and the webcam capture scheduler):

    0.0-0.9   camera power-up: rising square arpeggio + servo whirr + ready ding
    1.0/2.0/3.0  countdown beeps ("3... 2... 1...", rising pitch)
    4.0       SHUTTER: kchik double-click + body thump + motor wind
    4.75-6.3  sparkle success flourish

Pure numpy synthesis -> wav -> ffmpeg loudnorm -> mp3. Rerun after changing the
timeline: python3 tools/make_photobomb_audio.py
"""
import os
import subprocess
import sys
import tempfile
import wave

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from effects.photobomb_shot import BEEP_TIMES, DURATION, POWERUP_END, SHUTTER_OFFSET  # noqa: E402

SR = 44100
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, 'audio_files', 'photobomb-countdown.mp3')


def mix(buf, t0, sig):
    i = int(t0 * SR)
    buf[i:i + len(sig)] += sig[:max(0, len(buf) - i)]


def env_decay(n, tau):
    return np.exp(-np.arange(n) / (tau * SR))


def tone(freq, dur, tau=None, square=0.0):
    n = int(dur * SR)
    t = np.arange(n) / SR
    sig = np.sin(2 * np.pi * freq * t)
    if square:
        sig = (1 - square) * sig + square * np.sign(sig)
    if tau:
        sig *= env_decay(n, tau)
    else:
        # 5ms edges so raw tones don't click
        edge = int(0.005 * SR)
        sig[:edge] *= np.linspace(0, 1, edge)
        sig[-edge:] *= np.linspace(1, 0, edge)
    return sig


def main():
    rng = np.random.default_rng(1993)  # LotHT premiere year; deterministic output
    buf = np.zeros(int((DURATION + 0.3) * SR))

    # --- power-up: rising square arpeggio (retro camera boot) ---
    for i, (t0, f) in enumerate(zip([0.00, 0.18, 0.36, 0.54], [523.25, 659.25, 783.99, 1046.5])):
        mix(buf, t0, 0.28 * tone(f, 0.16, tau=0.10, square=0.6))
    # servo whirr rising underneath
    n = int(0.7 * SR)
    whirr = rng.standard_normal(n) * np.linspace(0.02, 0.09, n)
    whirr = np.diff(whirr, prepend=0)  # crude highpass -> thin electric hiss
    whirr *= 0.5 + 0.5 * np.sin(2 * np.pi * np.linspace(60, 140, n) * np.arange(n) / SR)
    mix(buf, 0.05, whirr)
    # ready ding
    mix(buf, POWERUP_END - 0.05, 0.30 * tone(1318.5, 0.5, tau=0.12))
    mix(buf, POWERUP_END - 0.05, 0.10 * tone(2637, 0.4, tau=0.08))

    # --- countdown beeps: 3... 2... 1... rising pitch ---
    for beep, f in zip(BEEP_TIMES, [880.0, 987.77, 1174.66]):
        mix(buf, beep, 0.42 * tone(f, 0.18, tau=0.30, square=0.35))

    # --- shutter at SHUTTER_OFFSET: kchik + thump + motor wind ---
    def burst(dur, amp, tau=0.006):
        n = int(dur * SR)
        return rng.standard_normal(n) * env_decay(n, tau) * amp
    mix(buf, SHUTTER_OFFSET, burst(0.030, 1.6))               # K-
    mix(buf, SHUTTER_OFFSET, 0.9 * tone(90, 0.10, tau=0.025))  # body thump
    mix(buf, SHUTTER_OFFSET + 0.050, burst(0.045, 1.3, tau=0.010))  # -CHIK
    mix(buf, SHUTTER_OFFSET + 0.050, 0.5 * tone(140, 0.08, tau=0.02))
    n = int(0.42 * SR)
    wind = rng.standard_normal(n) * env_decay(n, 0.35) * 0.45
    am_freq = np.linspace(120, 70, n)  # motor spinning down
    wind *= 0.55 + 0.45 * np.sin(2 * np.pi * np.cumsum(am_freq) / SR)
    wind = np.convolve(wind, np.ones(6) / 6, mode='same')  # soften
    mix(buf, SHUTTER_OFFSET + 0.12, wind)

    # --- sparkle flourish: glockenspiel arpeggio + closing chord ---
    for t0, f, a in zip([4.75, 4.95, 5.15, 5.35, 5.55],
                        [1046.5, 1318.5, 1568.0, 2093.0, 2637.0],
                        [0.30, 0.28, 0.26, 0.24, 0.22]):
        mix(buf, t0, a * tone(f, 0.6, tau=0.15))
        mix(buf, t0, a * 0.25 * tone(f * 3, 0.4, tau=0.05))
    for f in [1046.5, 1318.5, 1568.0, 2093.0]:
        mix(buf, 5.8, 0.16 * tone(f, 0.7, tau=0.25))

    # --- master ---
    buf = np.tanh(buf * 1.1)  # gentle limiter
    buf *= 0.92 / max(1e-9, np.abs(buf).max())
    fade = int(0.15 * SR)
    buf[-fade:] *= np.linspace(1, 0, fade)

    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
        with wave.open(tmp.name, 'wb') as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(SR)
            w.writeframes((buf * 32767).astype(np.int16).tobytes())
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', tmp.name,
                        '-af', 'loudnorm=I=-13:TP=-1.2:LRA=9',
                        '-ar', '44100', '-ac', '2', '-codec:a', 'libmp3lame', '-q:a', '2',
                        OUT], check=True)
        os.unlink(tmp.name)
    print(f"wrote {OUT} ({DURATION}s timeline: beeps at {BEEP_TIMES}, shutter at {SHUTTER_OFFSET})")


if __name__ == '__main__':
    main()
