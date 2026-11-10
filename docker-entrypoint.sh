#!/bin/bash
set -e

CMD="${1:-studio}"

if [ "$CMD" = "verify" ]; then
    echo "========================================================"
    echo "  RUNNING DOCKER CUDA & HARDWARE DIAGNOSTICS"
    echo "========================================================"
    exec python /app/scripts/verify_gpu.py

elif [ "$CMD" = "test" ] || [ "$CMD" = "transcribe-test" ]; then
    echo "========================================================"
    echo "  RUNNING WHISPER LARGE-V3 GPU TRANSCRIPTION TEST"
    echo "========================================================"
    exec python /app/scripts/transcribe_pipeline.py /app/input/test.wav --model large-v3

elif [ "$CMD" = "download" ]; then
    exec python /app/scripts/download_models.py --model large-v3

elif [ "$CMD" = "cli" ]; then
    shift
    exec python /app/scripts/transcribe_pipeline.py "$@"

elif [ "$CMD" = "studio-native" ]; then
    # Direct X11 display (for WSLg or Linux host with $DISPLAY set)
    exec python /app/scripts/ui.py

elif [ "$CMD" = "studio" ] || [ "$CMD" = "web" ]; then
    # Browser-accessible desktop GUI via noVNC
    echo "========================================================"
    echo "  STARTING LOCAL SPEECH STUDIO IN DOCKER"
    echo "  Web UI URL: http://localhost:6080"
    echo "========================================================"
    export DISPLAY=:1
    
    # Clean up any leftover X lock files
    rm -f /tmp/.X1-lock /tmp/.X11-unix/X1

    # 1. Start virtual frame buffer
    Xvfb :1 -screen 0 1280x820x24 &
    sleep 1

    # 2. Start lightweight window manager
    openbox &
    sleep 1

    # 3. Start VNC server (listening locally on 5900)
    x11vnc -display :1 -nopw -listen 127.0.0.1 -forever -shared &
    sleep 1

    # 4. Start websockify for noVNC
    websockify --web /usr/share/novnc 6080 localhost:5900 &
    sleep 1

    echo ">>> Studio Web UI is READY at http://localhost:6080 <<<"
    echo ">>> Open http://localhost:6080/vnc.html in your browser <<<"

    # 5. Launch the Studio UI
    exec python /app/scripts/ui.py

else
    exec "$@"
fi

