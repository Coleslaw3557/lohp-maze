FROM python:3.9-slim-buster

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    libsdl2-dev \
    libsdl2-mixer-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "main.py"]
