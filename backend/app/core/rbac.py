"""
Role-Based Access Control (RBAC).

Roles: user, admin.
"""

from __future__ import annotations

from enum import Enum
from typing import List


class Role(str, Enum):
    USER = "user"
    ADMIN = "admin"


# Permissions per endpoint group
PERMISSIONS = {
    "upload": [Role.USER, Role.ADMIN],
    "view_own_jobs": [Role.USER, Role.ADMIN],
    "view_own_attestations": [Role.USER, Role.ADMIN],
    "verify": [],  # public
    "admin_keys": [Role.ADMIN],
    "admin_revoke": [Role.ADMIN],
    "admin_anomalies": [Role.ADMIN],
    "delete_own_video": [Role.USER, Role.ADMIN],
    "share": [Role.USER, Role.ADMIN],
}


def has_permission(role: str, action: str) -> bool:
    """
    Check if a role has permission for an action.

    Public endpoints (empty permission list) always return True.
    """
    allowed = PERMISSIONS.get(action, [])
    if not allowed:
        return True  # public
    return Role(role) in allowed
