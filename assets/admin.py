from django.contrib import admin

from .models import Asset, Part, WorkOrder


@admin.register(Asset)
class AssetAdmin(admin.ModelAdmin):
    list_display = ("name", "organization", "manufacturer", "model_number", "location", "next_pm_date")
    list_filter = ("organization",)
    search_fields = ("name", "manufacturer", "model_number", "serial_number")


@admin.register(WorkOrder)
class WorkOrderAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "asset", "organization", "status", "technician", "created_at")
    list_filter = ("status", "organization")
    search_fields = ("title", "problem_description")


@admin.register(Part)
class PartAdmin(admin.ModelAdmin):
    list_display = ("part_number", "description", "category", "organization")
    list_filter = ("category", "organization")
    search_fields = ("part_number", "description")
