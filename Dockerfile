FROM python:3.9-slim-buster

# Set the working directory in the container
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libusb-1.0-0-dev \
    libasound2-dev \
    portaudio19-dev \
    i2c-tools \
    && rm -rf /var/lib/apt/lists/*

# Copy the current directory contents into the container at /app
COPY . /app

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Make ports 5000 and 8765 available to the world outside this container
EXPOSE 5000 8765

# Run app.py when the container launches
CMD ["python", "main.py"]
