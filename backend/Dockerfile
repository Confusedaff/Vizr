# Python is pinned to 3.11 deliberately, not just as a default: Coqui TTS
# (tts_engine.py's `from TTS.api import TTS`) hasn't been updated since
# Coqui AI shut down in January 2024, and its final release -- pinned
# below -- requires Python >=3.9,<3.12. Bumping this base image past 3.11
# will break the TTS install outright.
FROM python:3.11-slim

# System dependencies needed by Manim and TTS.
#
# fonts-jetbrains-mono matters beyond cosmetics: manim_renderer.py
# renders the submitted source code and all on-screen text in that font
# to match the app's own --font-mono design token. Without it actually
# installed, Pango silently falls back to a generic system font instead
# of raising an error -- the render still "works", it just doesn't look
# like the intended design. (Confirmed packaged for Debian bookworm,
# which this base image tracks: package fonts-jetbrains-mono 2.242+ds-3.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ffmpeg \
    libcairo2-dev \
    libpango1.0-dev \
    pkg-config \
    gcc \
    fonts-jetbrains-mono \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Manim (heavy — cached in its own layer). Pinned for
# reproducibility: manim_renderer.py's use of the Code mobject
# (the .code_lines attribute, the disable_ligatures workaround for
# JetBrains Mono) was written and verified against this exact version.
RUN pip install --no-cache-dir manim==0.20.1

# Install Coqui TTS (also heavy — cached in its own layer). Pinned to
# the final release published before Coqui AI's shutdown -- see the
# python:3.11-slim comment above for why this can't just float to
# "latest". tts_engine.py's TTS_MODEL_NAME env var lets you swap the
# actual voice model without touching this package pin.
RUN pip install --no-cache-dir TTS==0.22.0

COPY . .

# Create the media output directory
RUN mkdir -p /app/media

# Run as a non-root user. docker-compose.yml already sets
# cap_drop: ALL / no-new-privileges on this service — running as root
# on top of that is an unnecessary gap left over, especially for a
# container whose whole job is exec()'ing arbitrary submitted code
# (see tracer.py).
#
# OPERATIONAL NOTE: /app/media is bind-mounted from a host path in
# docker-compose.yml (the media_storage volume points at
# /home/server/codevisualizer/media on the host), so this chown only
# affects the image's own baked-in files — it does NOT change
# permissions on that host directory. Before deploying this, make sure
# the host directory is writable by uid 1000, e.g.:
#   sudo chown -R 1000:1000 /home/server/codevisualizer/media
# Skipping that step will make renders fail with a permission error
# writing the output video rather than a missing-file error, which is a
# confusing thing to debug after the fact if you're not expecting it.
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000
