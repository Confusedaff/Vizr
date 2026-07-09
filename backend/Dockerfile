FROM python:3.11-slim

# System dependencies needed by Manim and TTS
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libcairo2-dev \
    libpango1.0-dev \
    pkg-config \
    gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Manim (heavy — cached in its own layer)
RUN pip install --no-cache-dir manim

# Install Coqui TTS (also heavy — cached in its own layer)
RUN pip install --no-cache-dir TTS

COPY . .

# Create the media output directory
RUN mkdir -p /app/media

EXPOSE 8000