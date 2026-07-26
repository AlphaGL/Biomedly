"""Small helpers for the single-organization-per-user common case.

The data model (Membership) supports a user belonging to multiple orgs, but
the UI only ever surfaces the first one — simplest thing that works for a
small department, without blocking future multi-org support.
"""
from .models import Membership


def get_active_membership(user) -> Membership | None:
    if not user.is_authenticated:
        return None
    return user.memberships.select_related("organization").first()


def get_active_org(user):
    membership = get_active_membership(user)
    return membership.organization if membership else None


def is_org_admin(user) -> bool:
    membership = get_active_membership(user)
    return bool(membership and membership.role == "admin")
