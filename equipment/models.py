from django.conf import settings
from django.db import models


class Analysis(models.Model):
    """One 'Snap & Ask' request and its AI answer, kept as history."""

    MODE_CHOICES = [
        ("identify", "Identify the machine"),
        ("components", "Components & their roles"),
        ("board", "Board / PCB components"),
        ("function", "How it works"),
        ("troubleshoot", "Troubleshoot a problem"),
    ]
    LEVEL_CHOICES = [
        ("student", "Student"),
        ("technician", "Technician"),
        ("senior", "Senior engineer"),
    ]

    question = models.TextField(blank=True)
    mode = models.CharField(max_length=20, choices=MODE_CHOICES, default="identify")
    level = models.CharField(max_length=12, choices=LEVEL_CHOICES, default="technician")
    # Nullable: keeps existing rows valid and lets the app still work for a
    # user with no organization yet (shouldn't happen via signup, but the
    # FK shouldn't hard-fail if it does).
    organization = models.ForeignKey(
        "accounts.Organization", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="analyses",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="analyses",
    )
    equipment_name = models.CharField(max_length=200, blank=True)
    response_md = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "analyses"

    def __str__(self):
        return f"{self.get_mode_display()} — {self.equipment_name or self.question[:40]}"
