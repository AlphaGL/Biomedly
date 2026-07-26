import io

import qrcode
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST
from xhtml2pdf import pisa

from accounts.utils import get_active_org
from .models import Asset, Part, WorkOrder
from .services.suppliers import supplier_links


def _org_or_redirect(request):
    org = get_active_org(request.user)
    if not org:
        messages.warning(request, "You're not on a team yet.")
        return None
    return org


@login_required
def asset_list(request):
    org = _org_or_redirect(request)
    if not org:
        return redirect("accounts:signup")
    assets = org.assets.all()
    query = request.GET.get("q", "").strip()
    if query:
        from django.db.models import Q
        assets = assets.filter(
            Q(name__icontains=query) | Q(manufacturer__icontains=query)
            | Q(model_number__icontains=query) | Q(serial_number__icontains=query)
            | Q(location__icontains=query)
        )
    return render(request, "assets/list.html", {"assets": assets, "query": query})


@login_required
def asset_create(request):
    org = _org_or_redirect(request)
    if not org:
        return redirect("accounts:signup")
    if request.method == "POST":
        asset = Asset.objects.create(
            organization=org,
            name=request.POST.get("name", "").strip(),
            manufacturer=request.POST.get("manufacturer", "").strip(),
            model_number=request.POST.get("model_number", "").strip(),
            serial_number=request.POST.get("serial_number", "").strip(),
            location=request.POST.get("location", "").strip(),
            notes=request.POST.get("notes", "").strip(),
            next_pm_date=request.POST.get("next_pm_date") or None,
            photo=request.FILES.get("photo"),
            created_by=request.user,
        )
        messages.success(request, f"{asset.name} added to the register.")
        return redirect("assets:detail", pk=asset.pk)
    return render(request, "assets/form.html", {"asset": None})


@login_required
def asset_detail(request, pk):
    org = _org_or_redirect(request)
    if not org:
        return redirect("accounts:signup")
    asset = get_object_or_404(Asset, pk=pk, organization=org)
    work_orders = asset.work_orders.select_related("technician")
    qr_url = request.build_absolute_uri(reverse("assets:qr", args=[asset.pk]))
    return render(request, "assets/detail.html", {
        "asset": asset,
        "work_orders": work_orders,
        "qr_url": qr_url,
    })


@login_required
def asset_edit(request, pk):
    org = _org_or_redirect(request)
    if not org:
        return redirect("accounts:signup")
    asset = get_object_or_404(Asset, pk=pk, organization=org)
    if request.method == "POST":
        asset.name = request.POST.get("name", "").strip()
        asset.manufacturer = request.POST.get("manufacturer", "").strip()
        asset.model_number = request.POST.get("model_number", "").strip()
        asset.serial_number = request.POST.get("serial_number", "").strip()
        asset.location = request.POST.get("location", "").strip()
        asset.notes = request.POST.get("notes", "").strip()
        asset.next_pm_date = request.POST.get("next_pm_date") or None
        if request.FILES.get("photo"):
            asset.photo = request.FILES["photo"]
        asset.save()
        messages.success(request, "Updated.")
        return redirect("assets:detail", pk=asset.pk)
    return render(request, "assets/form.html", {"asset": asset})


@require_GET
def asset_qr(request, pk):
    """Public — this is what a phone camera hits when scanning the QR
    sticker, before the scanner necessarily has a session. It still lands
    on a login-gated detail page; only the code image itself is public."""
    asset = get_object_or_404(Asset, pk=pk)
    target_url = request.build_absolute_uri(reverse("assets:detail", args=[asset.pk]))
    img = qrcode.make(target_url)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return HttpResponse(buf.getvalue(), content_type="image/png")


@login_required
def workorder_create(request, asset_pk):
    org = _org_or_redirect(request)
    if not org:
        return redirect("accounts:signup")
    asset = get_object_or_404(Asset, pk=asset_pk, organization=org)
    if request.method == "POST":
        analysis_id = request.POST.get("linked_analysis_id") or None
        wo = WorkOrder.objects.create(
            organization=org,
            asset=asset,
            technician=request.user,
            title=request.POST.get("title", "").strip() or "Service call",
            problem_description=request.POST.get("problem_description", "").strip(),
            photo=request.FILES.get("photo"),
            linked_analysis_id=analysis_id,
        )
        messages.success(request, "Work order logged.")
        return redirect("assets:workorder_detail", pk=wo.pk)
    from equipment.models import Analysis
    recent_analyses = Analysis.objects.filter(organization=org).order_by("-created_at")[:15]
    return render(request, "assets/workorder_form.html", {
        "asset": asset, "recent_analyses": recent_analyses,
    })


@login_required
def workorder_detail(request, pk):
    org = _org_or_redirect(request)
    if not org:
        return redirect("accounts:signup")
    wo = get_object_or_404(WorkOrder, pk=pk, organization=org)
    return render(request, "assets/workorder_detail.html", {"wo": wo})


@login_required
@require_POST
def workorder_resolve(request, pk):
    org = _org_or_redirect(request)
    if not org:
        return redirect("accounts:signup")
    wo = get_object_or_404(WorkOrder, pk=pk, organization=org)
    wo.resolution_notes = request.POST.get("resolution_notes", "").strip()
    wo.status = "resolved"
    wo.resolved_at = timezone.now()
    wo.save()
    messages.success(request, "Work order marked resolved.")
    return redirect("assets:workorder_detail", pk=wo.pk)


@login_required
def workorder_pdf(request, pk):
    org = _org_or_redirect(request)
    if not org:
        return redirect("accounts:signup")
    wo = get_object_or_404(WorkOrder, pk=pk, organization=org)
    html = render_to_string("assets/workorder_pdf.html", {"wo": wo, "org": org})
    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="work-order-{wo.pk}.pdf"'
    pisa.CreatePDF(src=html, dest=response)
    return response


@login_required
def part_list(request):
    org = _org_or_redirect(request)
    if not org:
        return redirect("accounts:signup")
    from django.db.models import Q
    parts = Part.objects.filter(Q(organization=org) | Q(organization__isnull=True))
    query = request.GET.get("q", "").strip()
    if query:
        parts = parts.filter(Q(part_number__icontains=query) | Q(description__icontains=query))
    parts = parts.select_related("created_by")

    results = [{"part": p, "links": supplier_links(p.part_number)} for p in parts]
    web_links = supplier_links(query) if query else []
    return render(request, "assets/parts.html", {
        "results": results, "query": query, "web_links": web_links,
    })


@login_required
def part_create(request):
    org = _org_or_redirect(request)
    if not org:
        return redirect("accounts:signup")
    if request.method == "POST":
        Part.objects.create(
            organization=org,
            part_number=request.POST.get("part_number", "").strip(),
            description=request.POST.get("description", "").strip(),
            category=request.POST.get("category", "").strip(),
            notes=request.POST.get("notes", "").strip(),
            created_by=request.user,
        )
        messages.success(request, "Part added.")
        return redirect("assets:parts")
    return redirect("assets:parts")
