from django.urls import path

from . import views

app_name = "equipment"

urlpatterns = [
    path("", views.home, name="home"),
    path("history/", views.history, name="history"),
    path("api/search/", views.api_search, name="api_search"),
    path("api/device/", views.api_device_detail, name="api_device_detail"),
    path("api/guide/", views.api_guide_detail, name="api_guide_detail"),
    path("api/manuals/", views.api_find_manuals, name="api_find_manuals"),
    path("api/udi/", views.api_udi, name="api_udi"),
    path("api/analyze/", views.api_analyze, name="api_analyze"),
]
