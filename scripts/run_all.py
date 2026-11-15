"""
Master runner: install deps → generate data → download/mock weights → train all models → evaluate → export.

Usage (from project root):
    python scripts/run_all.py [--skip-install] [--skip-data] [--skip-weights] [--quick]

Flags:
    --skip-install  Skip pip install (if already done)
    --skip-data     Skip synthetic data generation
    --skip-weights  Skip mock weight download
    --quick         Use 2 epochs + minimal data for a quick smoke test
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VENV_PYTHON = ROOT / "venv" / "Scripts" / "python.exe"
VENV_PIP = ROOT / "venv" / "Scripts" / "pip.exe"


def run(cmd: list[str], cwd: Path = ROOT, check: bool = True) -> subprocess.CompletedProcess:
    print(f"\n{'='*60}")
    print(f"RUN: {' '.join(str(c) for c in cmd)}")
    print(f"{'='*60}")
    result = subprocess.run(cmd, cwd=cwd, text=True, capture_output=False)
    if check and result.returncode != 0:
        print(f"[ERROR] Command failed with code {result.returncode}")
        sys.exit(result.returncode)
    return result


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Master DeepFake detection runner")
    p.add_argument("--skip-install", action="store_true")
    p.add_argument("--skip-data", action="store_true")
    p.add_argument("--skip-weights", action="store_true")
    p.add_argument("--quick", action="store_true",
                   help="Quick smoke test: 2 epochs, minimal data")
    return p


def patch_config_for_quick(config_path: Path, epochs: int = 2, batch_size: int = 4) -> Path:
    """Write a quick-training variant of a yaml config."""
    import yaml
    with open(config_path) as f:
        cfg = yaml.safe_load(f)
    cfg["training"]["epochs"] = epochs
    cfg["training"]["patience"] = epochs
    cfg["training"]["batch_size"] = batch_size
    cfg["training"]["amp"] = False  # AMP not needed on CPU
    # Point data root to our synthetic data
    cfg["data"]["root"] = str(ROOT / "data" / "frames")
    cfg["data"]["num_workers"] = 0  # Avoid multiprocessing issues on Windows
    out_path = config_path.parent / f"_quick_{config_path.name}"
    with open(out_path, "w") as f:
        yaml.dump(cfg, f)
    print(f"[Config] Wrote quick config: {out_path}")
    return out_path


def patch_sequence_config_for_quick(config_path: Path, epochs: int = 2) -> Path:
    """Write a quick-training variant for sequence (BiGRU) config."""
    import yaml
    with open(config_path) as f:
        cfg = yaml.safe_load(f)
    cfg["training"]["epochs"] = epochs
    cfg["training"]["patience"] = epochs
    cfg["training"]["batch_size"] = 2
    cfg["training"]["amp"] = False
    # BiGRU uses features root (pre-extracted .pt files)
    cfg["data"]["root"] = str(ROOT / "data" / "features")
    cfg["data"]["num_workers"] = 0
    out_path = config_path.parent / f"_quick_{config_path.name}"
    with open(out_path, "w") as f:
        yaml.dump(cfg, f)
    print(f"[Config] Wrote quick BiGRU config: {out_path}")
    return out_path


def main() -> None:
    args = build_parser().parse_args()

    # -------------------------------------------------------------------------
    # 1. Install ML requirements
    # -------------------------------------------------------------------------
    if not args.skip_install:
        print("\n[Step 1] Installing ML requirements...")
        run([str(VENV_PIP), "install", "--quiet",
             "timm==1.0.12",
             "scikit-learn==1.5.2",
             "matplotlib==3.9.3",
             "seaborn==0.13.2",
             "pandas==2.2.3",
             "pyyaml==6.0.2",
             "Pillow==11.0.0",
        ])
        print("[Step 1] ML requirements installed.")
    else:
        print("[Step 1] Skipping install (--skip-install)")

    # -------------------------------------------------------------------------
    # 2. Generate synthetic data
    # -------------------------------------------------------------------------
    if not args.skip_data:
        print("\n[Step 2] Generating synthetic training data...")
        num_vids = 4 if args.quick else 20
        run([
            str(VENV_PYTHON), "scripts/create_synthetic_data.py",
            "--output-dir", str(ROOT / "data"),
            "--num-videos", str(num_vids),
            "--frames-per-video", "8" if args.quick else "15",
        ])
    else:
        print("[Step 2] Skipping data generation (--skip-data)")

    # -------------------------------------------------------------------------
    # 3. Generate mock weights
    # -------------------------------------------------------------------------
    if not args.skip_weights:
        print("\n[Step 3] Generating mock weights...")
        run([str(VENV_PYTHON), "scripts/download_weights.py",
             "--mock", "--output-dir", str(ROOT / "weights")])
    else:
        print("[Step 3] Skipping weight generation (--skip-weights)")

    # -------------------------------------------------------------------------
    # 4. Train models
    # -------------------------------------------------------------------------
    print("\n[Step 4] Training models...")

    import yaml
    sys.path.insert(0, str(ROOT))

    configs = {
        "EfficientNet-B4 (Spatial)": ROOT / "ml" / "configs" / "efficientnet_b4.yaml",
        "FrequencyCNN":              ROOT / "ml" / "configs" / "frequency_cnn.yaml",
    }
    seq_config = {
        "TemporalBiGRU": ROOT / "ml" / "configs" / "temporal_bigru.yaml",
    }

    for name, cfg_path in configs.items():
        print(f"\n--- Training: {name} ---")
        if args.quick:
            cfg_path = patch_config_for_quick(cfg_path)
        else:
            # Still patch data root and num_workers
            with open(cfg_path) as f:
                cfg = yaml.safe_load(f)
            cfg["data"]["root"] = str(ROOT / "data" / "frames")
            cfg["data"]["num_workers"] = 0
            cfg["training"]["amp"] = False
            patched = cfg_path.parent / f"_run_{cfg_path.name}"
            with open(patched, "w") as f:
                yaml.dump(cfg, f)
            cfg_path = patched

        run([str(VENV_PYTHON), "-m", "ml.train", "--config", str(cfg_path), "--device", "cpu"])

    for name, cfg_path in seq_config.items():
        print(f"\n--- Training: {name} ---")
        if args.quick:
            cfg_path = patch_sequence_config_for_quick(cfg_path)
        else:
            with open(cfg_path) as f:
                cfg = yaml.safe_load(f)
            cfg["data"]["root"] = str(ROOT / "data" / "features")
            cfg["data"]["num_workers"] = 0
            cfg["training"]["amp"] = False
            patched = cfg_path.parent / f"_run_{cfg_path.name}"
            with open(patched, "w") as f:
                yaml.dump(cfg, f)
            cfg_path = patched

        run([str(VENV_PYTHON), "-m", "ml.train", "--config", str(cfg_path), "--device", "cpu"])

    # -------------------------------------------------------------------------
    # 5. Run backend tests
    # -------------------------------------------------------------------------
    print("\n[Step 5] Running backend tests (crypto + API)...")
    run([str(VENV_PYTHON), "-m", "pytest",
         "backend/tests/", "-v", "--tb=short", "-q"], check=False)

    print("\n" + "="*60)
    print("ALL STEPS COMPLETE!")
    print("="*60)
    print(f"\nCheckpoints saved to: {ROOT / 'checkpoints'}")
    print(f"Weights saved to:      {ROOT / 'weights'}")
    print(f"\nTo start the backend:  cd {ROOT} && .\\venv\\Scripts\\uvicorn.exe backend.app.main:app --reload")
    print("API docs:              http://localhost:8000/docs")


if __name__ == "__main__":
    main()

