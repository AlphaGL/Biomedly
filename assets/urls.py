from django.urls import path

from . import views

app_name = "assets"

urlpatterns = [
    path("", views.asset_list, name="list"),
    path("new/", views.asset_create, name="create"),
    path("<int:pk>/", views.asset_detail, name="detail"),
    path("<int:pk>/edit/", views.asset_edit, name="edit"),
    path("<int:pk>/qr.png", views.asset_qr, name="qr"),
    path("<int:asset_pk>/workorders/new/", views.workorder_create, name="workorder_create"),
    path("workorders/<int:pk>/", views.workorder_detail, name="workorder_detail"),
    path("workorders/<int:pk>/resolve/", views.workorder_resolve, name="workorder_resolve"),
    path("workorders/<int:pk>/pdf/", views.workorder_pdf, name="workorder_pdf"),
    path("parts/", views.part_list, name="parts"),
    path("parts/new/", views.part_create, name="part_create"),
]
