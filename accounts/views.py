from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .models import Membership, Organization
from .utils import get_active_membership, get_active_org, is_org_admin


def signup(request):
    """Three paths, one form: solo (personal workspace), create a team
    (admin), or join a team via invite code (technician). All three end up
    as an Organization + Membership — "individual" is just a one-person
    org, so the data model doesn't need to know the difference, and a solo
    user can grow into a team later just by sharing their invite code."""
    if request.user.is_authenticated:
        return redirect("equipment:home")

    action = request.POST.get("action") or request.GET.get("action", "individual")
    if action not in ("individual", "create", "join"):
        action = "individual"

    if request.method == "POST":
        form = UserCreationForm(request.POST)
        org_name = request.POST.get("org_name", "").strip()
        invite_code = request.POST.get("invite_code", "").strip().upper()
        username = request.POST.get("username", "").strip()

        org = None
        role = "admin"
        org_error = None
        if action == "join":
            role = "technician"
            if not invite_code:
                org_error = "Enter your team's invite code."
            else:
                org = Organization.objects.filter(invite_code=invite_code).first()
                if not org:
                    org_error = "No team found with that invite code."
        elif action == "create":
            if not org_name:
                org_error = "Give your team a name."

        if form.is_valid() and not org_error:
            user = form.save()
            if action == "join":
                Membership.objects.create(user=user, organization=org, role=role)
            else:
                name = org_name if action == "create" else f"{username}'s workspace"
                org = Organization.objects.create(name=name)
                Membership.objects.create(user=user, organization=org, role="admin")
            login(request, user)
            messages.success(request, f"Welcome to {org.name}!")
            return redirect("equipment:home")
        if org_error:
            messages.error(request, org_error)
    else:
        form = UserCreationForm()

    return render(request, "accounts/signup.html", {"form": form, "action": action})


@login_required
def organization(request):
    membership = get_active_membership(request.user)
    if not membership:
        messages.warning(request, "You're not on a team yet.")
        return redirect("accounts:signup")

    org = membership.organization
    members = org.memberships.select_related("user").order_by("-role", "user__username")
    return render(request, "accounts/organization.html", {
        "org": org,
        "members": members,
        "is_admin": membership.role == "admin",
        "is_solo": members.count() == 1,
    })


@login_required
@require_POST
def regenerate_invite_code(request):
    if not is_org_admin(request.user):
        messages.error(request, "Only admins can do that.")
        return redirect("accounts:organization")
    org = get_active_org(request.user)
    from .models import _invite_code
    org.invite_code = _invite_code()
    org.save(update_fields=["invite_code"])
    messages.success(request, "Invite code regenerated.")
    return redirect("accounts:organization")


@login_required
@require_POST
def set_member_role(request, membership_id):
    if not is_org_admin(request.user):
        messages.error(request, "Only admins can do that.")
        return redirect("accounts:organization")
    org = get_active_org(request.user)
    membership = get_object_or_404(Membership, pk=membership_id, organization=org)
    role = request.POST.get("role")
    if role in dict(Membership.ROLE_CHOICES):
        membership.role = role
        membership.save(update_fields=["role"])
    return redirect("accounts:organization")


@login_required
@require_POST
def remove_member(request, membership_id):
    if not is_org_admin(request.user):
        messages.error(request, "Only admins can do that.")
        return redirect("accounts:organization")
    org = get_active_org(request.user)
    membership = get_object_or_404(Membership, pk=membership_id, organization=org)
    if membership.user_id != request.user.id:
        membership.delete()
    return redirect("accounts:organization")
