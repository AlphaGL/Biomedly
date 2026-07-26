import secrets

from django.conf import settings
from django.db import models


def _invite_code() -> str:
    return secrets.token_hex(4).upper()  # e.g. "A1B2C3D4"


class Organization(models.Model):
    """A department/team — the unit everything (assets, work orders, the
    shared knowledge base) is scoped to."""

    name = models.CharField(max_length=200)
    invite_code = models.CharField(max_length=12, unique=True, default=_invite_code)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Membership(models.Model):
    ROLE_CHOICES = [
        ("admin", "Admin"),
        ("technician", "Technician"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="memberships"
    )
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="memberships"
    )
    role = models.CharField(max_length=12, choices=ROLE_CHOICES, default="technician")
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("user", "organization")]

    def __str__(self):
        return f"{self.user} @ {self.organization} ({self.role})"
