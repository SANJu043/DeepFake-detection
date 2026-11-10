"""
Download pretrained model weights for deepfake detection.

Since this is a university demo project, this script creates
placeholder/random weights for local testing when real pretrained
weights are not available.

For production use, replace URLs with actual model hosting.

Usage:
    python scripts/download_weights.py [--output-dir ./weights] [--mock]
"""

from __future__ import annotations

import argparse
import hashlib
import sys
import urllib.request
from pathlib import Path
from typing import Dict, Optional

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# ---------------------------------------------------------------------------
# Weight file registry
# Each entry: filename -> real download URL (or None when not yet hosted).
# Replace the None values with actual URLs for a production deployment.
# ---------------------------------------------------------------------------

WEIGHT_REGISTRY: Dict[str, Optional[str]] = {
    "spatial.pt": None,     # EfficientNetB4Detector
    "frequency.pt": None,   # FrequencyCNN
    "temporal.pt": None,    # TemporalBiGRU
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def sha256_file(path: Path) -> str:
    """Return the hex SHA-256 digest of a file."""
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def human_size(n_bytes: int) -> str:
    """Return a human-readable file size string (KB / MB / GB)."""
    for unit in ("B", "KB", "MB", "GB"):
        if n_bytes < 1024:
            return f"{n_bytes:.1f} {unit}"
        n_bytes /= 1024  # type: ignore[assignment]
    return f"{n_bytes:.1f} TB"


def print_file_summary(path: Path) -> None:
    """Print path, size, and SHA-256 for a saved weight file."""
    size = path.stat().st_size
    digest = sha256_file(path)
    print(f"    Path   : {path}")
    print(f"    Size   : {human_size(size)}")
    print(f"    SHA256 : {digest}")


# ---------------------------------------------------------------------------
# Mock weights (random initialization)
# ---------------------------------------------------------------------------


def save_mock_weights(output_dir: Path) -> None:
    """Create randomly-initialised weight files for local testing.

    Uses the actual model classes so the state_dict shapes are correct.
    The weights are *not* trained – they are only useful for verifying that
    the inference pipeline loads and runs without errors.
    """
    # Deferred import: torch / ml.models are heavy; skip if --mock is not used
    try:
        import torch
        from ml.models.efficientnet_b4 import EfficientNetB4Detector
        from ml.models.frequency_cnn import FrequencyCNN
        from ml.models.temporal_bigru import TemporalBiGRU
    except ImportError as exc:
        print(
            f"[ERROR] Could not import required modules: {exc}\n"
            "        Make sure you are running from the project root with the "
            "ml package on PYTHONPATH.",
            file=sys.stderr,
        )
        sys.exit(1)

    model_map = {
        "spatial.pt": EfficientNetB4Detector(pretrained=False),
        "frequency.pt": FrequencyCNN(),
        "temporal.pt": TemporalBiGRU(),
    }

    output_dir.mkdir(parents=True, exist_ok=True)

    for filename, model in model_map.items():
        dest = output_dir / filename
        model.eval()
        torch.save(model.state_dict(), dest)
        label = type(model).__name__
        print(f"  [MOCK] {label} → {filename}")
        print_file_summary(dest)
        print()


# ---------------------------------------------------------------------------
# Real download
# ---------------------------------------------------------------------------


def download_weights(output_dir: Path, registry: Dict[str, Optional[str]]) -> None:
    """Download weight files from the URLs listed in *registry*.

    Files whose URL is ``None`` are skipped with a warning.  Already-existing
    files are skipped to avoid redundant downloads.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    any_missing = False

    for filename, url in registry.items():
        dest = output_dir / filename

        if url is None:
            print(
                f"  [SKIP] {filename}: no download URL configured.\n"
                f"         Set a real URL in WEIGHT_REGISTRY or use --mock.",
                file=sys.stderr,
            )
            any_missing = True
            continue

        if dest.exists():
            print(f"  [SKIP] {filename}: already exists at {dest}")
            continue

        print(f"  [DL]   {filename}")
        print(f"         URL: {url}")

        try:
            urllib.request.urlretrieve(url, dest)
        except Exception as exc:
            print(f"  [ERROR] Download failed: {exc}", file=sys.stderr)
            if dest.exists():
                dest.unlink()   # Remove partial file
            continue

        print_file_summary(dest)
        print()

    if any_missing:
        print(
            "\n[WARNING] Some weights were not downloaded because no URL is "
            "configured.\n"
            "          Run with --mock to generate random placeholder weights,\n"
            "          or add real URLs to WEIGHT_REGISTRY in this script.",
            file=sys.stderr,
        )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Download (or mock) pretrained deepfake detection model weights."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("./weights"),
        metavar="DIR",
        help="Directory where weight files will be saved.",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        default=False,
        help=(
            "Generate randomly-initialised placeholder weights instead of "
            "downloading real pretrained weights. Useful for local dev/CI."
        ),
    )
    return parser


def main(argv: Optional[list] = None) -> None:
    args = build_parser().parse_args(argv)

    print(f"Output directory : {args.output_dir.resolve()}")
    print(f"Mode             : {'mock (random init)' if args.mock else 'download'}\n")

    if args.mock:
        save_mock_weights(args.output_dir)
    else:
        all_urls_missing = all(url is None for url in WEIGHT_REGISTRY.values())
        if all_urls_missing:
            print(
                "[INFO] No download URLs are configured. Falling back to --mock mode.\n"
                "       To use real weights, set URLs in WEIGHT_REGISTRY inside this script.",
                file=sys.stderr,
            )
            save_mock_weights(args.output_dir)
        else:
            download_weights(args.output_dir, WEIGHT_REGISTRY)

    print("Done.")


if __name__ == "__main__":
    main()
