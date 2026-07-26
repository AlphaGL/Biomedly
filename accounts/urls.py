from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("signup/", views.signup, name="signup"),
    path("login/", auth_views.LoginView.as_view(template_name="accounts/login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(next_page="accounts:login"), name="logout"),
    path("org/", views.organization, name="organization"),
    path("org/invite/regenerate/", views.regenerate_invite_code, name="regenerate_invite_code"),
    path("org/member/<int:membership_id>/role/", views.set_member_role, name="set_member_role"),
    path("org/member/<int:membership_id>/remove/", views.remove_member, name="remove_member"),
]
