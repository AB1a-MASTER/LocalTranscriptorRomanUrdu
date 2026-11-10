# =============================================================================
# Local Speech Studio — Ultra-Lean Docker GPU Distribution (~2.5 GB)
# Base: NVIDIA CUDA 12.1.1 + cuDNN 8 Runtime on Ubuntu 22.04
# Optimized: CTranslate2 native GPU inference (eliminates 15GB PyTorch bloat)
# =============================================================================
FROM nvidia/cuda:12.1.1-cudnn8-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV NVIDIA_VISIBLE_DEVICES=all
ENV NVIDIA_DRIVER_CAPABILITIES=compute,utility
ENV LC_ALL=C.UTF-8
ENV LANG=C.UTF-8

# Install minimal system runtime: Python 3.10, FFmpeg, Tkinter, X11 virtual buffer, and noVNC
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.10 \
    python3-pip \
    python3-tk \
    tk \
    tcl \
    ffmpeg \
    libsndfile1 \
    libasound2 \
    alsa-utils \
    xvfb \
    x11vnc \
    openbox \
    novnc \
    websockify \
    ca-certificates \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# Configure python and python3 to point to python3.10
RUN update-alternatives --install /usr/bin/python python /usr/bin/python3.10 1 \
    && update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.10 1

WORKDIR /app

# Upgrade pip and install lightweight CPU PyTorch (~180MB) for tokenization/utility
# (CTranslate2 handles GPU acceleration natively via /usr/local/cuda; avoids 14GB CUDA PyTorch stack)
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

# Install project Python dependencies
COPY requirements-docker.txt .
RUN pip install --no-cache-dir -r requirements-docker.txt && \
    find /usr -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

# Copy source code and default input (filtered via .dockerignore)
COPY scripts/ /app/scripts/
COPY input/ /app/input/

# Create persistent mount directories
RUN mkdir -p /app/output /root/.cache/huggingface

# Setup entrypoint script
COPY docker-entrypoint.sh /app/docker-entrypoint.sh
RUN chmod +x /app/docker-entrypoint.sh

# Expose noVNC port for web-based GUI
EXPOSE 6080

ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["studio"]
