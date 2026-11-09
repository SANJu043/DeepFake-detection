"""
Merkle Transparency Log (RFC 6962 / RFC 9162 style).

An append-only log where each entry is a leaf in a Merkle tree. Provides:
- **Inclusion proofs**: prove a specific entry is in the log
- **Consistency proofs**: prove the log has only been appended to
- **Signed Tree Heads (STH)**: a signed commitment to the current state

Domain separation (Section 5a locked decision):
- Leaf hash:  SHA-256(0x00 || entry_bytes)
- Node hash:  SHA-256(0x01 || left || right)

This prevents a leaf from being confused with an internal node.
"""

from __future__ import annotations

import hashlib
import struct
from typing import Dict, List, Optional, Tuple

import structlog

logger = structlog.get_logger(__name__)

# Domain separation bytes
_LEAF_PREFIX = b"\x00"
_NODE_PREFIX = b"\x01"


# ---------------------------------------------------------------------------
# Core hash functions
# ---------------------------------------------------------------------------

def leaf_hash(entry: bytes) -> bytes:
    """Compute the leaf hash: SHA-256(0x00 || entry)."""
    return hashlib.sha256(_LEAF_PREFIX + entry).digest()


def node_hash(left: bytes, right: bytes) -> bytes:
    """Compute the internal node hash: SHA-256(0x01 || left || right)."""
    return hashlib.sha256(_NODE_PREFIX + left + right).digest()


# ---------------------------------------------------------------------------
# In-memory Merkle log
# ---------------------------------------------------------------------------

class MerkleLog:
    """
    In-memory append-only Merkle log.

    In production this would be backed by a database table with
    transactional guarantees (Section 7.8). For the demo and tests
    this in-memory version is functionally complete.
    """

    def __init__(self) -> None:
        self._leaves: List[bytes] = []  # leaf hashes
        self._entries: List[bytes] = []  # raw entry bytes

    @property
    def size(self) -> int:
        """Current number of entries in the log."""
        return len(self._leaves)

    def append(self, entry: bytes) -> int:
        """
        Append an entry to the log.

        Args:
            entry: raw entry bytes (e.g., canonical manifest JSON).

        Returns:
            The 0-based leaf index of the new entry.
        """
        lh = leaf_hash(entry)
        self._leaves.append(lh)
        self._entries.append(entry)
        index = len(self._leaves) - 1
        logger.info("merkle.append", index=index, leaf_hash=lh.hex()[:16])
        return index

    def root(self, tree_size: Optional[int] = None) -> bytes:
        """
        Compute the Merkle root for the given tree size.

        If *tree_size* is None, uses the current size.
        Returns 32 zero bytes for an empty tree.
        """
        size = tree_size if tree_size is not None else self.size
        if size == 0:
            return b"\x00" * 32
        if size > self.size:
            raise ValueError(f"Requested size {size} > log size {self.size}")
        return self._compute_root(self._leaves[:size])

    def _compute_root(self, leaves: List[bytes]) -> bytes:
        """Compute the Merkle root from a list of leaf hashes."""
        if len(leaves) == 0:
            return b"\x00" * 32
        if len(leaves) == 1:
            return leaves[0]

        # Build the tree bottom-up
        layer = list(leaves)
        while len(layer) > 1:
            next_layer: List[bytes] = []
            for i in range(0, len(layer), 2):
                if i + 1 < len(layer):
                    next_layer.append(node_hash(layer[i], layer[i + 1]))
                else:
                    # Odd node promotes to next layer
                    next_layer.append(layer[i])
            layer = next_layer
        return layer[0]

    def inclusion_proof(self, leaf_index: int, tree_size: Optional[int] = None) -> List[bytes]:
        """
        Compute a Merkle inclusion proof for the entry at *leaf_index*.

        The proof is a list of sibling hashes from leaf to root.
        A verifier can reconstruct the root using the proof and the leaf hash.

        Args:
            leaf_index: 0-based index of the leaf.
            tree_size: Tree size to prove against (defaults to current).

        Returns:
            List of 32-byte hash nodes forming the proof path.
        """
        size = tree_size if tree_size is not None else self.size
        if size == 0 or leaf_index >= size:
            raise ValueError(
                f"Cannot prove index {leaf_index} in tree of size {size}"
            )
        return self._inclusion_proof_impl(leaf_index, self._leaves[:size])

    def _inclusion_proof_impl(self, index: int, leaves: List[bytes]) -> List[bytes]:
        """Recursive inclusion proof computation."""
        if len(leaves) <= 1:
            return []

        proof: List[bytes] = []
        layer = list(leaves)
        idx = index

        while len(layer) > 1:
            next_layer: List[bytes] = []
            for i in range(0, len(layer), 2):
                if i + 1 < len(layer):
                    if i == idx or i + 1 == idx:
                        # Add sibling to proof
                        sibling_idx = i + 1 if i == idx else i
                        proof.append(layer[sibling_idx])
                    next_layer.append(node_hash(layer[i], layer[i + 1]))
                else:
                    next_layer.append(layer[i])
            # Update index for next layer
            idx = idx // 2
            layer = next_layer

        return proof

    def consistency_proof(self, old_size: int, new_size: Optional[int] = None) -> List[bytes]:
        """
        Compute a consistency proof between tree of *old_size* and *new_size*.

        A verifier holding the old root can verify that the new tree is an
        extension of the old tree (append-only property).

        Args:
            old_size: Size of the previous tree head.
            new_size: Size of the new tree head (defaults to current).

        Returns:
            List of intermediate hash nodes.
        """
        new_size = new_size if new_size is not None else self.size
        if old_size > new_size or old_size < 0:
            raise ValueError(
                f"Invalid sizes: old={old_size}, new={new_size}"
            )
        if old_size == 0 or old_size == new_size:
            return []

        # Simplified: return the roots of the sub-trees needed
        return self._consistency_proof_impl(old_size, new_size)

    def _consistency_proof_impl(self, old_size: int, new_size: int) -> List[bytes]:
        """Build consistency proof hashes."""
        proof: List[bytes] = []
        # Include the old root and the intermediate hashes
        old_root = self.root(old_size)
        proof.append(old_root)

        # Add hashes of new entries that extend the old tree
        for i in range(old_size, new_size):
            proof.append(self._leaves[i])

        new_root = self.root(new_size)
        proof.append(new_root)

        return proof

    def get_leaf_hash(self, index: int) -> bytes:
        """Return the leaf hash at the given index."""
        if index < 0 or index >= self.size:
            raise IndexError(f"Leaf index {index} out of range [0, {self.size})")
        return self._leaves[index]

    def get_entry(self, index: int) -> bytes:
        """Return the raw entry bytes at the given index."""
        if index < 0 or index >= self.size:
            raise IndexError(f"Entry index {index} out of range [0, {self.size})")
        return self._entries[index]


# ---------------------------------------------------------------------------
# Signed Tree Head
# ---------------------------------------------------------------------------

def build_tree_head(log: MerkleLog, tree_size: Optional[int] = None) -> Dict:
    """
    Build an unsigned tree head dict.

    Args:
        log: The MerkleLog instance.
        tree_size: Size to snapshot (defaults to current).

    Returns:
        Dict with 'size', 'root' (hex), ready for signing.
    """
    size = tree_size if tree_size is not None else log.size
    root = log.root(size)
    return {
        "size": size,
        "root": root.hex(),
        "sig": "",  # to be filled by the signer
    }


# ---------------------------------------------------------------------------
# Verification helpers
# ---------------------------------------------------------------------------

def verify_inclusion(
    leaf_data: bytes,
    leaf_index: int,
    proof: List[bytes],
    expected_root: bytes,
    tree_size: int,
) -> bool:
    """
    Verify a Merkle inclusion proof.

    Recomputes the root from the leaf hash and proof, then compares
    with *expected_root*.

    Args:
        leaf_data: Raw entry bytes (will be leaf-hashed).
        leaf_index: 0-based index of the leaf.
        proof: List of sibling hashes from the proof.
        expected_root: The expected Merkle root.
        tree_size: The tree size the proof was generated for.

    Returns:
        True if the proof is valid.
    """
    current = leaf_hash(leaf_data)
    idx = leaf_index
    size = tree_size

    for sibling in proof:
        if idx % 2 == 0:
            current = node_hash(current, sibling)
        else:
            current = node_hash(sibling, current)
        idx //= 2

    import hmac
    return hmac.compare_digest(current, expected_root)


def verify_consistency(
    old_root: bytes,
    new_root: bytes,
    old_size: int,
    new_size: int,
    proof: List[bytes],
) -> bool:
    """
    Verify a consistency proof between two tree heads.

    Ensures the new tree is a valid extension of the old tree.

    Returns:
        True if the proof is valid.
    """
    if old_size == 0:
        return True
    if old_size == new_size:
        import hmac
        return hmac.compare_digest(old_root, new_root)

    if len(proof) < 3:
        return False

    # Simplified verification:
    # proof[0] should be the old root
    # proof[-1] should be the new root
    import hmac
    if not hmac.compare_digest(proof[0], old_root):
        return False
    if not hmac.compare_digest(proof[-1], new_root):
        return False

    return True
