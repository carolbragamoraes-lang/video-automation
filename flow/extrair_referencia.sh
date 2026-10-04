#!/usr/bin/env bash
# Extrai metadados e um grid de quadros (1 por segundo) de um vídeo de referência.
# Uso: flow/extrair_referencia.sh <video.mp4> <pasta_projeto>
set -euo pipefail
VID="$1"; OUT="$2"
mkdir -p "$OUT/referencia"
ffprobe -v error -show_entries format=duration:stream=codec_type,width,height,r_frame_rate \
  -of compact "$VID" | tee "$OUT/referencia/metadados.txt"
DUR=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$VID")
N=$(python3 -c "import math;print(max(1,math.ceil($DUR)))")
ROWS=$(( (N + 5) / 6 ))
ffmpeg -v error -y -i "$VID" -vf "fps=1,scale=240:-1,tile=6x${ROWS}" -frames:v 1 "$OUT/referencia/grid.png"
ffmpeg -v error -y -i "$VID" -ac 1 -ar 16000 "$OUT/referencia/audio.wav"
echo "ok: $OUT/referencia/grid.png ($N quadros), audio.wav"
