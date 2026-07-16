FROM python:3.11-slim-bookworm

WORKDIR /app

# libusb runtime for the FTDI USB-DMX interface (pyftdi)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libusb-1.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app

EXPOSE 5000 8765

CMD ["python", "main.py"]
