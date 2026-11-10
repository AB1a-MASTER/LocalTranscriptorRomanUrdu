#!/bin/bash
# =============================================================================
# Local Speech Studio — Docker GPU Helper for Linux / WSL2
# =============================================================================

ACTION="${1:-help}"

mkdir -p input output cache/huggingface

case "$ACTION" in
    build)
        echo "Building local-speech-studio:gpu..."
        docker build -t local-speech-studio:gpu .
        ;;
    verify)
        echo "Verifying NVIDIA GPU and CUDA..."
        docker run --rm --gpus all local-speech-studio:gpu verify
        ;;
    test)
        echo "Running Whisper Large-v3 test on input/test.wav..."
        docker run --rm --gpus all \
            -v "$(pwd)/input:/app/input" \
            -v "$(pwd)/output:/app/output" \
            -v "$(pwd)/cache/huggingface:/root/.cache/huggingface" \
            local-speech-studio:gpu test
        ;;
    studio)
        echo "Starting Studio container (Web UI on port 6080)..."
        docker compose up -d studio
        echo "Open in browser: http://localhost:6080/vnc.html"
        ;;
    studio-native)
        echo "Starting Studio with native X11/WSLg display..."
        docker run --rm --gpus all \
            -e DISPLAY="$DISPLAY" \
            -v /tmp/.X11-unix:/tmp/.X11-unix \
            -v "$(pwd)/input:/app/input" \
            -v "$(pwd)/output:/app/output" \
            -v "$(pwd)/cache/huggingface:/root/.cache/huggingface" \
            local-speech-studio:gpu studio-native
        ;;
    stop)
        echo "Stopping containers..."
        docker compose down
        ;;
    *)
        echo "Usage: ./docker_run.sh [build|verify|test|studio|studio-native|stop]"
        ;;
esac

