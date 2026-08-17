FROM python:3.11-slim-bookworm

WORKDIR /app

# libusb runtime for the FTDI USB-DMX interface (pyftdi);
# fswebcam grabs Photo Bomb stills from the USB webcam (camera_manager.py);
# dejavu + tzdata for the photos' Pacific-time corner watermark;
# ffmpeg preps the ESP32 node ambience streams (audio_manager crossfade/offset
# WAVs — first missed on the 2026-08-16 Monkey Room bring-up, bench servers
# always had it from the host)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libusb-1.0-0 \
    fswebcam \
    fonts-dejavu-core \
    tzdata \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app

EXPOSE 5000 8765

CMD ["python", "main.py"]
