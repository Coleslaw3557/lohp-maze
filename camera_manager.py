"""USB webcam capture for the Photo Bomb room.

The camera plugs into the server Pi (USB); the room's ESP32 button fires the
PhotoBomb-Shot effect over the normal trigger contract, and main.py schedules a
capture at the effect's shutter moment. Photos land in ``photos_dir`` — the
Pi's SD card by default — named ``photobomb_YYYY-MM-DD_HH-MM-SS.jpg``.

Optional ``camera_config.json`` at the repo root overrides DEFAULT_CONFIG.

Capture backends, tried in order (first usable wins):
  fswebcam    tiny purpose-built V4L2 grabber (installed in the Docker image)
  ffmpeg      one-frame v4l2 grab
  synthetic   no camera hardware: writes an SMPTE-bars placeholder JPEG so the
              whole flow stays testable in the sim / dev environment
"""
import asyncio
import base64
import json
import logging
import os
import shutil
import subprocess
from datetime import datetime

logger = logging.getLogger(__name__)

DEFAULT_CONFIG = {
    "device": "/dev/video0",
    "resolution": "1280x720",
    "photos_dir": "photos",
    # start the grabber this early: device open + auto-exposure warm-up eats
    # most of a second on cheap webcams, and we want the frame AT the flash
    "capture_lead_time": 1.0,
    # clients need a beat to start playback; land the photo just after the
    # shutter sound people actually hear
    "shutter_latency_compensation": 0.25,
    "backend": "auto",   # auto | fswebcam | ffmpeg | synthetic
}

# SMPTE bars, 640x360 — written by the synthetic backend when no camera exists
_PLACEHOLDER_JPEG = base64.b64decode("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")


class CameraManager:
    def __init__(self, config_file='camera_config.json'):
        self.config = dict(DEFAULT_CONFIG)
        try:
            with open(config_file) as f:
                self.config.update(json.load(f))
        except FileNotFoundError:
            pass
        except (json.JSONDecodeError, OSError) as e:
            logger.error(f"Ignoring bad {config_file}: {e}")
        self.photos_dir = os.path.abspath(self.config['photos_dir'])
        os.makedirs(self.photos_dir, exist_ok=True)
        self._pending = None  # asyncio.Task of the scheduled capture, if any
        self.backend = self._pick_backend()
        logger.info(f"CameraManager ready: backend={self.backend} device={self.config['device']} "
                    f"photos_dir={self.photos_dir}")

    def _pick_backend(self):
        want = self.config.get('backend', 'auto')
        if want != 'auto':
            return want
        if os.path.exists(self.config['device']):
            if shutil.which('fswebcam'):
                return 'fswebcam'
            if shutil.which('ffmpeg'):
                return 'ffmpeg'
            logger.warning(f"{self.config['device']} exists but no fswebcam/ffmpeg found; "
                           "photos will be synthetic placeholders")
        return 'synthetic'

    # ---- scheduling (called from effect hooks; event-loop thread only) ----

    def schedule_capture(self, delay_s):
        """(Re)schedule a capture ``delay_s`` after now — the effect's shutter
        moment. A button re-press restarts the countdown (the effect task is
        superseded), so any pending capture is replaced, never doubled."""
        self.cancel_pending()
        self._pending = asyncio.create_task(self._capture_later(delay_s))

    def cancel_pending(self):
        """Drop the scheduled capture (countdown was cancelled/superseded)."""
        if self._pending and not self._pending.done():
            self._pending.cancel()
            logger.info("Pending photo capture cancelled")
        self._pending = None

    async def _capture_later(self, delay_s):
        lead = self.config['capture_lead_time'] if self.backend != 'synthetic' else 0.0
        await asyncio.sleep(max(0.0, delay_s + self.config['shutter_latency_compensation'] - lead))
        try:
            path = await self.capture()
            logger.info(f"Photo captured: {path}")
        except Exception as e:
            logger.error(f"Photo capture failed: {e}")

    # ---- capture ----

    async def capture(self):
        """Grab one frame to a timestamped file; returns the path."""
        ts = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        path = os.path.join(self.photos_dir, f'photobomb_{ts}.jpg')
        seq = 1
        while os.path.exists(path):  # burst within the same second
            path = os.path.join(self.photos_dir, f'photobomb_{ts}-{seq}.jpg')
            seq += 1
        await asyncio.get_running_loop().run_in_executor(None, self._grab, path)
        return path

    def _grab(self, path):
        dev, res = self.config['device'], self.config['resolution']
        if self.backend == 'fswebcam':
            # -S skips warm-up frames so auto-exposure settles before the shot
            cmd = ['fswebcam', '-d', dev, '-r', res, '-S', '10',
                   '--no-banner', '--jpeg', '92', path]
        elif self.backend == 'ffmpeg':
            cmd = ['ffmpeg', '-v', 'error', '-y', '-f', 'v4l2', '-video_size', res,
                   '-i', dev, '-frames:v', '1', path]
        else:
            with open(path, 'wb') as f:
                f.write(_PLACEHOLDER_JPEG)
            return
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        if result.returncode != 0 or not os.path.exists(path):
            raise RuntimeError(f"{self.backend} capture failed: {result.stderr.strip()[:300]}")

    # ---- listing (for /api/photobomb/photos) ----

    def list_photos(self):
        photos = []
        for name in os.listdir(self.photos_dir):
            if not name.lower().endswith('.jpg'):
                continue
            st = os.stat(os.path.join(self.photos_dir, name))
            photos.append({
                'filename': name,
                'size_bytes': st.st_size,
                'taken_at': datetime.fromtimestamp(st.st_mtime).isoformat(timespec='seconds'),
            })
        photos.sort(key=lambda p: p['taken_at'], reverse=True)
        return photos
