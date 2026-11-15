"""
Train Model 3 (TemporalBiGRU) on the real video sequence features,
evaluate it, and export all 3 models to TorchScript for production deployment.
"""

import subprocess
import sys
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PYTHON = ROOT / "venv" / "Scripts" / "python.exe"

def run_cmd(cmd, desc):
    print(f"\n{'='*60}")
    print(f"  {desc}")
    print(f"{'='*60}\n", flush=True)
    res = subprocess.run(cmd, cwd=ROOT)
    if res.returncode != 0:
        print(f"FAILED: {desc} (exit code {res.returncode})")
        sys.exit(res.returncode)
    print(f"\nSUCCESS: {desc}\n")

# 1. Train TemporalBiGRU
run_cmd(
    [str(PYTHON), "-m", "ml.train", "--config", "ml/configs/_train_real_temporal_bigru.yaml", "--device", "cpu"],
    "TRAIN MODEL 3: TemporalBiGRU on Real Celeb-DF Video Sequences"
)

# 2. Evaluate TemporalBiGRU
run_cmd(
    [
        str(PYTHON), "-m", "ml.evaluate",
        "--config", "ml/configs/_train_real_temporal_bigru.yaml",
        "--weights", "checkpoints/temporal_bigru_best.pt",
        "--device", "cpu",
        "--output", "checkpoints/eval_real_temporal_bigru.json"
    ],
    "EVALUATE MODEL 3: TemporalBiGRU"
)

# 3. Export all 3 models to TorchScript
exports = [
    ("spatial", "checkpoints/efficientnet_b4_best.pt", "checkpoints/spatial_scripted.pt"),
    ("frequency", "checkpoints/frequency_cnn_best.pt", "checkpoints/frequency_scripted.pt"),
    ("temporal", "checkpoints/temporal_bigru_best.pt", "checkpoints/temporal_scripted.pt"),
]

for model_type, weights, out in exports:
    run_cmd(
        [
            str(PYTHON), "-m", "ml.export",
            "--model", model_type,
            "--weights", weights,
            "--format", "torchscript",
            "--output", out,
            "--device", "cpu"
        ],
        f"EXPORT {model_type.upper()} TO TORCHSCRIPT"
    )

print("\nALL MODEL TRAINING, EVALUATION, AND EXPORTS ARE 100% COMPLETE!")
