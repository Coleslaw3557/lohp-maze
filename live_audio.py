"""Shared realtime bed broadcast — the radio model for node audio sync.

2026-08-31 (Tim, on-playa): rooms playing the same background MUST play
together. The per-node offset streams (serve_audio ?offset_s=) start each box
at the right position, but every box then drifts by its own start latency,
RF-stutter underruns, and reconnect staggering — after an hour of playa WiFi
flapping, boxes were minutes apart.

This module runs ONE ffmpeg per bed file, encoding in realtime (-re) and
looping forever; every node streams the SAME live edge:

  * a joining node (fresh dispatch, reconnect, watchdog re-dispatch) starts
    at *now* — no offset math, no per-node ffmpeg;
  * a node that stalls on RF falls behind in its queue; past ~3s of backlog
    it is KICKED (stream closed) instead of replaying stale audio. The node
    reports IDLE, the bed watchdog re-dispatches, and it rejoins at the live
    edge. Skew between boxes stays bounded at roughly the node's startup
    buffer (~0.5-1 s) instead of growing without limit.

Only LOOPING beds ride this (node_audio_manager._live_url): a once-through
maze window keeps the offset path so its once_pad_s tail still goes quiet.
Music in ESP flash stays off the table (Tim) — this is server-side only.

Everything runs on the event loop (create_subprocess_exec — the 2026-08
freeze rule: no blocking subprocess on the loop).
"""
import asyncio
import hashlib
import logging
import time
from collections import deque

logger = logging.getLogger(__name__)

CHUNK = 4096                 # ~0.25s @128kbps
CLIENT_QUEUE_CHUNKS = 12     # kick a client ~3s behind the live edge
RING_CHUNKS = 2              # burst to a new joiner: primes decode, ~0.5s lag
IDLE_REAP_S = 180            # encoder with no listeners this long is stopped
RESTART_BACKOFF_S = 2.0
BITRATE = '128k'


class _Client:
    def __init__(self):
        self.queue = asyncio.Queue(maxsize=CLIENT_QUEUE_CHUNKS)
        self.dead = False
        self.skips = 0

    def push(self, chunk):
        """Feed one chunk. A client whose TCP stalled past the queue depth is
        NOT torn down (a kick meant a stream teardown + a ~12s watchdog gap
        on every playa RF stutter): its backlog is discarded and it resumes
        at the live edge. MP3 decoders resync on the next frame header — a
        brief garble, and the box is back in time with everyone else."""
        if self.dead:
            return
        try:
            self.queue.put_nowait(chunk)
        except asyncio.QueueFull:
            dropped = 0
            try:
                while True:
                    self.queue.get_nowait()
                    dropped += 1
            except asyncio.QueueEmpty:
                pass
            try:
                self.queue.put_nowait(chunk)
            except asyncio.QueueFull:
                pass
            self.skips += dropped
        return

    def close(self):
        self.dead = True
        try:
            self.queue.put_nowait(None)
        except asyncio.QueueFull:
            try:
                self.queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
            try:
                self.queue.put_nowait(None)
            except asyncio.QueueFull:
                pass


class _Channel:
    def __init__(self, key, path, loop):
        self.key = key
        self.path = path
        self.loop = loop
        self.finished = False     # once-mode channel reached file end
        self.clients = set()
        self.ring = deque(maxlen=RING_CHUNKS)
        self.idle_since = time.monotonic()
        self.task = asyncio.create_task(self._run())

    async def _run(self):
        while True:
            proc = None
            try:
                loop_args = ['-stream_loop', '-1'] if self.loop else []
                proc = await asyncio.create_subprocess_exec(
                    'ffmpeg', '-hide_banner', '-loglevel', 'error',
                    '-re', *loop_args,
                    '-i', self.path,
                    '-vn', '-codec:a', 'libmp3lame', '-b:a', BITRATE,
                    '-f', 'mp3', 'pipe:1',
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE)
                logger.info(f"Live bed up [{self.key}] "
                            f"({'loop' if self.loop else 'once'}): {self.path}")
                last_skip_report = 0.0
                while True:
                    chunk = await proc.stdout.read(CHUNK)
                    if not chunk:
                        break
                    self.ring.append(chunk)
                    for client in self.clients:
                        client.push(chunk)
                    now = time.monotonic()
                    total_skips = sum(c.skips for c in self.clients)
                    if total_skips and now - last_skip_report > 60:
                        last_skip_report = now
                        logger.info(f"Live bed [{self.key}]: laggards skipped "
                                    f"{total_skips} chunks to the live edge "
                                    f"({len(self.clients)} listeners)")
                        for c in self.clients:
                            c.skips = 0
                stderr = (await proc.stderr.read()).decode(errors='replace')[:300]
                if not self.loop:
                    # Once-mode: the file simply ended. Close every listener
                    # (their once_pad_s tail goes quiet, matching the offset
                    # path) and tombstone the channel until the next window
                    # dispatches a fresh key.
                    self.finished = True
                    for client in list(self.clients):
                        client.close()
                    self.clients.clear()
                    self.idle_since = time.monotonic()
                    logger.info(f"Live bed [{self.key}] finished (once mode)")
                    return
                logger.warning(f"Live bed [{self.key}] encoder ended: {stderr}")
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error(f"Live bed [{self.key}] died: {e}", exc_info=True)
            finally:
                if proc is not None and proc.returncode is None:
                    proc.terminate()
                    try:
                        await asyncio.wait_for(proc.wait(), 2)
                    except asyncio.TimeoutError:
                        proc.kill()
                        await proc.wait()
            await asyncio.sleep(RESTART_BACKOFF_S)

    def open(self):
        client = _Client()
        for chunk in self.ring:
            client.push(chunk)
        self.clients.add(client)
        return client

    def drop(self, client):
        client.dead = True
        self.clients.discard(client)
        if not self.clients:
            self.idle_since = time.monotonic()

    def stop(self):
        self.task.cancel()
        for client in list(self.clients):
            client.close()
        self.clients.clear()


class LiveAudioHub:
    def __init__(self):
        self.channels = {}   # key -> _Channel
        self._reaper = None

    @staticmethod
    def key_for(path, loop):
        return hashlib.sha1(f"{'L' if loop else 'O'}:{path}".encode()).hexdigest()[:16]

    def ensure(self, path, loop=True):
        """Start (or keep) the live channel for `path`; returns its key."""
        key = self.key_for(path, loop)
        channel = self.channels.get(key)
        # A finished once-channel (task done) is replaced too: the rotation
        # re-picking the same file must play it again, not hit the tombstone.
        if channel is None or channel.task.done():
            self.channels[key] = _Channel(key, path, loop)
        else:
            channel.idle_since = time.monotonic()
        if self._reaper is None or self._reaper.done():
            self._reaper = asyncio.create_task(self._reap())
        return key

    def open(self, key):
        """Attach a listener. Returns (queue, close_fn) or None."""
        channel = self.channels.get(key)
        if channel is None or channel.finished or channel.task.done():
            return None
        client = channel.open()
        return client.queue, (lambda: channel.drop(client))

    async def _reap(self):
        while True:
            await asyncio.sleep(30)
            now = time.monotonic()
            for key, channel in list(self.channels.items()):
                if (not channel.clients
                        and now - channel.idle_since > IDLE_REAP_S):
                    logger.info(f"Live bed [{key}] idle {IDLE_REAP_S}s — stopping")
                    channel.stop()
                    self.channels.pop(key, None)
