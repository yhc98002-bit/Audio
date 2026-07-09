#!/usr/bin/env bash
# Detached launcher for the ADSR downstream watch loop.
# Must activate audio-prm so torch/demucs/torchaudio resolve (nohup spawns a bare shell).
set +e
# Use the env's python binary directly — robust against conda-activate no-ops under nohup.
# (audio-prm site-packages carry torch 2.5.1 / demucs / torchaudio; Demucs runs CPU-only.)
PYBIN=/HOME/paratera_xy/pxy1289/.conda/envs/audio-prm/bin/python
cd /HOME/paratera_xy/pxy1289/HDD_POOL/HaocunYe/Research/AudioDiffusion
exec "$PYBIN" scripts/adsr_downstream.py watch --workers 12 --threads 4 --interval 300
