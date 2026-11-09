"""
Revocation service (Section 7.7 and FR13).

Manages attestation revocations. A signed revocation list is served publicly
so verifiers can check if an attestation has been revoked.

Verifiers fail closed: if the revocation list is unreachable and the cached
copy is older than 24 hours, verification fails.
"""

from __future__ import annotations

import base64
import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

import jcs
import structlog

from backend.app.services.signer import SignerBackend

logger = structlog.get_logger(__name__)


@dataclass
class RevocationEntry:
    """A single revocation record."""

    attestation_id: str
    reason: str
    revoked_by: str
    revoked_at: str  # RFC 3339 UTC
    list_version: int


@dataclass
class SignedRevocationList:
    """
    A signed, versioned list of revoked attestations.

    The list is signed by the same signer used for attestations,
    ensuring non-repudiation.
    """

    version: int
    entries: List[Dict[str, Any]]
    issued_at: str
    signature: str  # base64 Ed25519 over canonical(entries + version + issued_at)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "entries": self.entries,
            "issued_at": self.issued_at,
            "signature": self.signature,
        }


class RevocationService:
    """
    In-memory revocation service.

    In production this would be backed by the ``revocations`` database table.
    """

    def __init__(self, signer: SignerBackend) -> None:
        self._signer = signer
        self._revoked: Dict[str, RevocationEntry] = {}
        self._version = 0

    def revoke(
        self,
        attestation_id: str,
        reason: str,
        revoked_by: str,
    ) -> RevocationEntry:
        """
        Revoke an attestation.

        Args:
            attestation_id: UUID of the attestation to revoke.
            reason: Human-readable reason for revocation.
            revoked_by: UUID of the user or admin performing the revocation.

        Returns:
            The RevocationEntry.

        Raises:
            ValueError: If already revoked.
        """
        if attestation_id in self._revoked:
            raise ValueError(f"Attestation {attestation_id} is already revoked")

        self._version += 1
        entry = RevocationEntry(
            attestation_id=attestation_id,
            reason=reason,
            revoked_by=revoked_by,
            revoked_at=datetime.now(timezone.utc).isoformat(),
            list_version=self._version,
        )
        self._revoked[attestation_id] = entry
        logger.info(
            "revocation.created",
            attestation_id=attestation_id,
            reason=reason,
            revoked_by=revoked_by,
        )
        return entry

    def is_revoked(self, attestation_id: str) -> bool:
        """Check if an attestation has been revoked."""
        return attestation_id in self._revoked

    def get_revocation(self, attestation_id: str) -> Optional[RevocationEntry]:
        """Get the revocation entry for an attestation, if revoked."""
        return self._revoked.get(attestation_id)

    def signed_list(self) -> SignedRevocationList:
        """
        Produce a signed revocation list.

        The signature covers the canonical JSON of the list content,
        ensuring integrity and non-repudiation.
        """
        entries = [
            {
                "attestation_id": e.attestation_id,
                "reason": e.reason,
                "revoked_by": e.revoked_by,
                "revoked_at": e.revoked_at,
            }
            for e in self._revoked.values()
        ]

        issued_at = datetime.now(timezone.utc).isoformat()

        # Build signable content
        signable = {
            "version": self._version,
            "entries": entries,
            "issued_at": issued_at,
        }
        signable_bytes = jcs.canonicalize(signable)
        sig = self._signer.sign(signable_bytes)

        return SignedRevocationList(
            version=self._version,
            entries=entries,
            issued_at=issued_at,
            signature=base64.b64encode(sig).decode(),
        )

    def verify_list(
        self,
        revocation_list: SignedRevocationList,
        public_key_pem: str,
    ) -> bool:
        """
        Verify the signature on a revocation list.

        Returns:
            True if the signature is valid.
        """
        from backend.app.services.signer import verify_with_public_key

        signable = {
            "version": revocation_list.version,
            "entries": revocation_list.entries,
            "issued_at": revocation_list.issued_at,
        }
        signable_bytes = jcs.canonicalize(signable)
        sig_bytes = base64.b64decode(revocation_list.signature)
        return verify_with_public_key(signable_bytes, sig_bytes, public_key_pem)
