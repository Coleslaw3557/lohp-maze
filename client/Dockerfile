FROM python:3.9-slim-buster

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    python3-dev \
    ffmpeg \
    vlc \
    libasound2-dev \
    portaudio19-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN mkdir -p /app/cache/audio_files

CMD ["python", "main.py"]
