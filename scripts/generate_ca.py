#!/usr/bin/env python3
"""
Generate demo CA and signing certificates for local development.

Creates:
- Self-signed root CA
- Signing key pair (Ed25519)
- TSA key pair (Ed25519)

Usage:
    python scripts/generate_ca.py [--output-dir ./keys]
"""

from __future__ import annotations

import argparse
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


def generate_keypair(key_dir: Path, name: str) -> None:
    """Generate an Ed25519 key pair and write PEM files."""
    key_dir.mkdir(parents=True, exist_ok=True)

    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()

    priv_path = key_dir / f"{name}_private.pem"
    pub_path = key_dir / f"{name}_public.pem"

    priv_path.write_bytes(
        private_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    priv_path.chmod(0o600)

    pub_path.write_bytes(
        public_key.public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )

    print(f"  ✓ {priv_path}")
    print(f"  ✓ {pub_path}")


def main():
    parser = argparse.ArgumentParser(description="Generate demo CA and signing keys")
    parser.add_argument("--output-dir", default="./keys", help="Output directory")
    args = parser.parse_args()

    base = Path(args.output_dir)

    print("Generating signing key pair...")
    generate_keypair(base, "ed25519")

    print("\nGenerating TSA key pair...")
    tsa_dir = base / "tsa"
    generate_keypair(tsa_dir, "tsa")

    print(f"\n✅ All keys generated in: {base.resolve()}")
    print("⚠️  These are demo keys. For production, use a proper CA / HSM.")


if __name__ == "__main__":
    main()
