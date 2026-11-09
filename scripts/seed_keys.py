"""
Generate Ed25519 signing keys and TSA keys for development.

Creates:
    keys/signing_private.pem
    keys/signing_public.pem
    keys/tsa/tsa_private.pem
    keys/tsa/tsa_public.pem

Usage:
    python scripts/seed_keys.py [--output-dir ./keys]
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import sys
from pathlib import Path
from typing import Optional, Tuple

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


# ---------------------------------------------------------------------------
# Key generation helpers
# ---------------------------------------------------------------------------


def generate_ed25519_keypair() -> Tuple[Ed25519PrivateKey, bytes, bytes]:
    """Generate a fresh Ed25519 keypair.

    Returns
    -------
    private_key:
        The :class:`Ed25519PrivateKey` object (keep in memory, never log it).
    private_pem:
        PEM-encoded private key bytes (PKCS8, no encryption).
    public_pem:
        PEM-encoded public key bytes (SubjectPublicKeyInfo).
    """
    private_key = Ed25519PrivateKey.generate()

    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return private_key, private_pem, public_pem


def public_key_fingerprint(private_key: Ed25519PrivateKey) -> str:
    """Return the SHA-256 fingerprint of the public key (DER, base64-encoded).

    This matches the format used by tools like ``ssh-keygen -lf``.

    Parameters
    ----------
    private_key:
        The private key whose corresponding public key will be fingerprinted.

    Returns
    -------
    str
        ``"SHA256:<base64>"`` fingerprint string.
    """
    public_key = private_key.public_key()
    der = public_key.public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    digest = hashlib.sha256(der).digest()
    b64 = base64.b64encode(digest).decode("ascii").rstrip("=")
    return f"SHA256:{b64}"


def write_key_pair(
    output_dir: Path,
    private_filename: str,
    public_filename: str,
    label: str,
) -> None:
    """Generate an Ed25519 keypair and write both PEM files to *output_dir*.

    Parameters
    ----------
    output_dir:
        Directory where the PEM files will be written.
    private_filename:
        Filename for the private key PEM (e.g. ``"signing_private.pem"``).
    public_filename:
        Filename for the public key PEM (e.g. ``"signing_public.pem"``).
    label:
        Human-readable label printed in the console summary.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    private_path = output_dir / private_filename
    public_path = output_dir / public_filename

    # Warn and skip if keys already exist to avoid silently rotating live creds
    if private_path.exists() or public_path.exists():
        print(
            f"  [SKIP] {label}: key file(s) already exist in {output_dir} – "
            "delete them manually to regenerate.",
            file=sys.stderr,
        )
        return

    private_key, private_pem, public_pem = generate_ed25519_keypair()
    fingerprint = public_key_fingerprint(private_key)

    private_path.write_bytes(private_pem)
    public_path.write_bytes(public_pem)

    # Restrict private key permissions (owner read-only) on POSIX systems
    try:
        private_path.chmod(0o600)
    except NotImplementedError:
        pass  # Windows – skip chmod

    print(f"  {label}")
    print(f"    Private : {private_path}")
    print(f"    Public  : {public_path}")
    print(f"    Fingerprint: {fingerprint}")


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def seed_keys(output_dir: Path) -> None:
    """Generate all keypairs for the deepfake-auth dev environment.

    Parameters
    ----------
    output_dir:
        Root key directory (usually ``./keys`` relative to the project root).
    """
    print(f"Generating Ed25519 keys in: {output_dir.resolve()}\n")

    # 1. Application signing keys
    write_key_pair(
        output_dir=output_dir,
        private_filename="signing_private.pem",
        public_filename="signing_public.pem",
        label="Signing keypair",
    )

    # 2. TSA (Timestamp Authority) keys
    write_key_pair(
        output_dir=output_dir / "tsa",
        private_filename="tsa_private.pem",
        public_filename="tsa_public.pem",
        label="TSA keypair",
    )

    print("\nDone.")
    print(
        "\n[!] Keep the private key files out of version control.\n"
        "    Add 'keys/' to your .gitignore if you haven't already."
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate Ed25519 signing and TSA keys for development.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("./keys"),
        metavar="DIR",
        help="Root directory where key files will be written.",
    )
    return parser


def main(argv: Optional[list] = None) -> None:
    args = build_parser().parse_args(argv)
    seed_keys(args.output_dir)


if __name__ == "__main__":
    main()
