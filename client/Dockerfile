FROM python:3.11-slim-bookworm

WORKDIR /app

# gcc/python3-dev: build RPi.GPIO; vlc: audio playback; i2c-tools: ADS1115 debugging
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    vlc \
    i2c-tools \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app

RUN mkdir -p /app/cache/audio_files

CMD ["python", "main.py"]
