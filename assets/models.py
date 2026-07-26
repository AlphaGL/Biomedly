import uuid

from django.conf import settings
from django.db import models

from accounts.models import Organization


def asset_photo_path(instance, filename):
    return f"assets/{instance.organization_id}/{filename}"


def workorder_photo_path(instance, filename):
    return f"workorders/{instance.organization_id}/{filename}"


class Asset(models.Model):
    """One piece of equipment your department owns — the system-of-record
    entry that a QR code on the machine links to."""

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="assets")
    name = models.CharField(max_length=200, help_text="e.g. OR-3 Patient Monitor")
    manufacturer = models.CharField(max_length=150, blank=True)
    model_number = models.CharField(max_length=150, blank=True)
    serial_number = models.CharField(max_length=150, blank=True)
    location = models.CharField(max_length=200, blank=True, help_text="e.g. OR-3, 2nd floor")
    notes = models.TextField(blank=True)
    photo = models.ImageField(upload_to=asset_photo_path, blank=True, null=True)
    next_pm_date = models.DateField(blank=True, null=True, verbose_name="Next PM due")
    qr_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.model_number})" if self.model_number else self.name

    @property
    def full_name(self) -> str:
        parts = [p for p in [self.manufacturer, self.model_number] if p]
        return " ".join(parts) or self.name


class WorkOrder(models.Model):
    """A permanent, exportable service record tied to an asset — this is
    what makes the app audit-ready rather than just a lookup tool."""

    STATUS_CHOICES = [
        ("open", "Open"),
        ("in_progress", "In Progress"),
        ("resolved", "Resolved"),
    ]

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="work_orders")
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name="work_orders")
    technician = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="work_orders"
    )
    title = models.CharField(max_length=200)
    problem_description = models.TextField(blank=True)
    resolution_notes = models.TextField(blank=True)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default="open")
    photo = models.ImageField(upload_to=workorder_photo_path, blank=True, null=True)
    linked_analysis = models.ForeignKey(
        "equipment.Analysis",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="work_orders",
        help_text="The AI troubleshooting conversation this work order came from, if any.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"WO-{self.pk}: {self.title}"


class Part(models.Model):
    """A part your team has identified — with auto-generated supplier
    search links. The cross-reference data itself is curated over time
    (via /admin/); we can't source a live distributor catalog for free."""

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="parts", null=True, blank=True,
        help_text="Blank = visible to every team (a shared generic part).",
    )
    part_number = models.CharField(max_length=120)
    description = models.CharField(max_length=250, blank=True)
    category = models.CharField(max_length=120, blank=True, help_text="e.g. Capacitor, Fuse, Sensor")
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["part_number"]

    def __str__(self):
        return self.part_number
