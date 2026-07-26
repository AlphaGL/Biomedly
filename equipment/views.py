from __future__ import annotations

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db import connection
from django.http import JsonResponse
from django.shortcuts import render

from django.views.decorators.http import require_GET, require_POST

from accounts.utils import get_active_org
from .models import Analysis
from .services import ai, ifixit, manuals, openfda

ALLOWED_IMAGE_TYPES = {
    "image/jpeg": "image/jpeg",
    "image/png": "image/png",
    "image/webp": "image/webp",
    "image/gif": "image/gif",
}
ALLOWED_VIDEO_TYPES = {
    "video/mp4": "video/mp4",
    "video/webm": "video/webm",
    "video/quicktime": "video/quicktime",  # .mov from phones
    "video/3gpp": "video/3gpp",
}
MAX_IMAGES = 4
MAX_VIDEOS = 1
# Gemini inline requests cap at ~20 MB total; leave headroom for the prompt.
MAX_VIDEO_SIZE = 18 * 1024 * 1024


def home(request):
    """Open to everyone — the AI assistant and research tools need no
    account. Team features (assets, work orders, shared history) are what
    require signing up; see the banner in the template."""
    return render(request, "equipment/home.html")


@login_required
def history(request):
    """The team knowledge base: every analysis your whole org has run,
    searchable — not just your own. When your colleague fixes something,
    it's findable here the next time anyone hits the same fault."""
    org = get_active_org(request.user)
    analyses = Analysis.objects.filter(organization=org) if org else Analysis.objects.none()

    query = request.GET.get("q", "").strip()
    if query:
        if connection.vendor == "postgresql":
            from django.contrib.postgres.search import SearchQuery, SearchVector
            analyses = analyses.annotate(
                search=SearchVector("equipment_name", "question", "response_md")
            ).filter(search=SearchQuery(query))
        else:
            from django.db.models import Q
            analyses = analyses.filter(
                Q(equipment_name__icontains=query) | Q(question__icontains=query)
                | Q(response_md__icontains=query)
            )

    return render(request, "equipment/history.html", {
        "analyses": analyses.select_related("user")[:50],
        "query": query,
    })


@require_GET
def api_search(request):
    """Aggregate iFixit + openFDA results for an equipment name.

    Falls back to a simplified query (e.g. brand without the model number)
    when iFixit has no exact match — flagged via ``exact``/``effective_query``.
    """
    query = request.GET.get("q", "").strip()
    if not query:
        return JsonResponse({"error": "Missing query"}, status=400)

    ifixit_results = ifixit.search_with_fallback(query)
    return JsonResponse({
        "query": query,
        "effective_query": ifixit_results["effective_query"],
        "exact": ifixit_results["exact"],
        "guides": ifixit_results["guides"],
        "devices": ifixit_results["devices"],
        "classification": openfda.classify_device(query),
        "recalls": openfda.recent_recalls(query),
    })


@require_GET
def api_device_detail(request):
    """Full iFixit device wiki page, rendered on our site."""
    title = request.GET.get("title", "").strip()
    if not title:
        return JsonResponse({"error": "Missing title"}, status=400)
    device = ifixit.get_device(title)
    if not device:
        return JsonResponse({"error": "Device page not found on iFixit."}, status=404)
    return JsonResponse({"device": device})


@require_GET
def api_find_manuals(request):
    """Manuals for an exact model: Google web search + a no-key fallback link.

    Complements the iFixit-attached documents already shown on device pages
    — this covers models iFixit's community never uploaded anything for.
    """
    model = request.GET.get("model", "").strip()
    if not model:
        return JsonResponse({"error": "Missing model"}, status=400)

    return JsonResponse({
        "model": model,
        "manuals": manuals.search_manuals(model),
        "google_url": manuals.google_search_url(model),
    })


@require_GET
def api_guide_detail(request):
    """Full iFixit repair guide with steps and images."""
    guideid = request.GET.get("id", "").strip()
    if not guideid.isdigit():
        return JsonResponse({"error": "Missing or invalid guide id"}, status=400)
    guide = ifixit.get_guide(int(guideid))
    if not guide:
        return JsonResponse({"error": "Guide not found on iFixit."}, status=404)
    return JsonResponse({"guide": guide})


@require_GET
def api_udi(request):
    """Identify a device from the UDI barcode number printed on it."""
    udi = request.GET.get("udi", "").strip()
    if not udi:
        return JsonResponse({"error": "Missing UDI"}, status=400)
    device = openfda.lookup_udi(udi)
    if not device:
        return JsonResponse({"error": "No device found for that UDI."}, status=404)
    return JsonResponse({"device": device})


MAX_HISTORY_TURNS = 8
MAX_TURN_CHARS = 6000


def _parse_history(raw: str) -> list[dict]:
    """Validate the conversation history sent by the frontend."""
    import json

    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        return []
    if not isinstance(data, list):
        return []
    turns = []
    for item in data[-MAX_HISTORY_TURNS:]:
        if not isinstance(item, dict):
            continue
        role = item.get("role")
        text = item.get("text")
        if role in ("user", "assistant") and isinstance(text, str) and text.strip():
            turns.append({"role": role, "text": text[:MAX_TURN_CHARS]})
    return turns


@require_POST
def api_analyze(request):
    """Snap & Ask: photos (optional, processed in memory only) + question -> AI guide."""
    question = request.POST.get("question", "").strip()
    mode = request.POST.get("mode", "identify")
    level = request.POST.get("level", "technician")
    equipment_name = request.POST.get("equipment_name", "").strip()
    history = _parse_history(request.POST.get("history", ""))
    if mode not in dict(Analysis.MODE_CHOICES):
        mode = "identify"
    if level not in dict(Analysis.LEVEL_CHOICES):
        level = "technician"

    image_uploads = request.FILES.getlist("images")
    video_uploads = request.FILES.getlist("videos")
    if len(image_uploads) > MAX_IMAGES:
        return JsonResponse(
            {"error": f"Too many photos — maximum is {MAX_IMAGES}."}, status=400
        )
    if len(video_uploads) > MAX_VIDEOS:
        return JsonResponse(
            {"error": f"Only {MAX_VIDEOS} video per question."}, status=400
        )

    # Media is read into memory for the AI call and never written to disk.
    media: list[tuple[bytes, str]] = []
    for upload in image_uploads:
        if upload.size > settings.MAX_UPLOAD_SIZE:
            return JsonResponse(
                {"error": f"'{upload.name}' is too large (max 10 MB per photo)."},
                status=400,
            )
        mime = ALLOWED_IMAGE_TYPES.get(upload.content_type)
        if not mime:
            return JsonResponse(
                {"error": f"'{upload.name}': unsupported type. Use JPEG, PNG, WebP or GIF."},
                status=400,
            )
        media.append((upload.read(), mime))

    for upload in video_uploads:
        if upload.size > MAX_VIDEO_SIZE:
            return JsonResponse(
                {"error": f"'{upload.name}' is too large. Keep videos under 18 MB "
                          "(about 30-60 seconds at phone quality)."},
                status=400,
            )
        mime = ALLOWED_VIDEO_TYPES.get(upload.content_type)
        if not mime:
            return JsonResponse(
                {"error": f"'{upload.name}': unsupported video type. Use MP4, WebM or MOV."},
                status=400,
            )
        media.append((upload.read(), mime))

    if video_uploads and not ai._gemini_keys():
        return JsonResponse(
            {"error": "Video analysis requires a Gemini API key."}, status=400
        )

    if not media and not question and not equipment_name:
        return JsonResponse(
            {"error": "Provide a photo/video, an equipment name, or a question."},
            status=400,
        )

    # Only fetch grounding data on the first turn — follow-ups reuse the
    # context already baked into the conversation. A single common word
    # (e.g. "hello") can fuzzy-match an unrelated real iFixit device (there
    # really is a "Nest Hello" doorbell) and waste a round trip on garbage
    # context — only fall back to the raw question if it looks like an
    # actual equipment reference (2+ words), not small talk.
    grounding_query = equipment_name or (question if len(question.split()) >= 2 else "")
    context = "" if (history or not grounding_query) else ai.build_context(grounding_query)

    try:
        result = ai.analyze(
            question=question,
            mode=mode,
            level=level,
            media=media,
            history=history,
            context=context,
        )
    except ai.AIKeyMissing as exc:
        return JsonResponse({"error": str(exc)}, status=503)
    except Exception:
        return JsonResponse(
            {"error": "AI analysis failed. Check your API key and internet connection, then try again."},
            status=502,
        )

    record = Analysis.objects.create(
        question=question,
        mode=mode,
        level=level,
        equipment_name=equipment_name,
        response_md=result["answer"],
        organization=get_active_org(request.user),
        user=request.user if request.user.is_authenticated else None,
    )

    return JsonResponse({
        "id": record.id,
        "answer": result["answer"],
        "followups": result["followups"],
    })
