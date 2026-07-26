from django.contrib import admin

from .models import Analysis


@admin.register(Analysis)
class AnalysisAdmin(admin.ModelAdmin):
    list_display = ("id", "mode", "equipment_name", "question", "created_at")
    list_filter = ("mode", "created_at")
    search_fields = ("equipment_name", "question", "response_md")
