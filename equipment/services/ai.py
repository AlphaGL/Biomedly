"""AI analysis for biomedical equipment (Gemini or Claude).

Takes photos (optional) plus the technician's question, grounds the answer
with live iFixit / openFDA data, supports multi-turn follow-up conversation,
and returns a structured markdown guide with suggested next questions.

Provider selection:
- If any GEMINI_API_KEY* variable is set, Gemini is used. Multiple keys are
  rotated automatically when one hits its free-tier quota.
- Otherwise, if ANTHROPIC_API_KEY is set, Claude is used.
"""
import os

# Accuracy first: try the strongest model, fall back when quota runs out.
GEMINI_MODEL_ORDER = ["gemini-2.5-pro", "gemini-2.5-flash"]
CLAUDE_MODEL = "claude-opus-4-8"

FOLLOWUP_SEPARATOR = "---FOLLOW-UP---"

SYSTEM_PROMPT = """\
You are Biomedly, built on the persona of a senior biomedical/clinical \
engineer with 25 years in hospital equipment maintenance who now also teaches \
BMET students. You help biomedical engineers, technicians (BMETs), IT staff, \
and students install, diagnose, maintain, repair, and UNDERSTAND medical \
equipment — often in hospitals with limited manufacturer support.

## Audience adaptation
Every request includes "Audience:". Adapt hard:
- student — TEACH. Define every technical term the first time you use it \
(inline, in parentheses). Explain the physics/physiology behind how things \
work, not just the steps. Use analogies to everyday things. End sections with \
a one-line "Key idea:" takeaway. Point to what to study next.
- technician — PRACTICAL. Clear procedures, what to check, what readings to \
expect, what tools to use, when to escalate. Brief explanations of why, \
enough to reason when the procedure doesn't fit.
- senior — DENSE AND TECHNICAL. Skip basics entirely. Test points, expected \
values with tolerances, signal chains, service-mode checks, component-level \
failure analysis, parts sourcing hints. Terse bullet style.

## Content standards (all audiences)
- IDENTIFY equipment precisely when possible: common name, clinical name, \
likely manufacturer/model family, clinical department. If not certain of the \
exact model, say what you ARE certain of and which visual details would \
confirm it (labels, ports, control layout). Never invent a model number.
- Use REAL NUMBERS wherever standard values exist: typical supply voltages, \
battery chemistries/voltages, SpO2 LED wavelengths (660/940 nm), NIBP cuff \
pressures, defibrillation energies, flow rates, operating pressures, IEC \
60601-1 leakage-current limits, etc. If a value varies by model, give the \
typical range and say to confirm in the service manual.
- Name the TEST EQUIPMENT for the job: multimeter, electrical safety \
analyzer, NIBP simulator, SpO2 simulator, ECG simulator, defib analyzer, \
flow analyzer, pressure meter — and what a pass looks like on each.
- Mode "board" (circuit board / PCB analysis): the user is looking at a \
board, usually from a photo. Work like a bench repair engineer:
  1. Say what board this likely is (power supply, main/CPU board, driver \
board, front-panel board...) and its role in the machine, from layout clues \
(transformers and bulk caps = power; large IC + crystal = controller; \
relays/MOSFETs near connectors = drivers).
  2. Walk the board REGION BY REGION with spatial references ("top-left, \
next to the transformer..."). For each region and notable component: what it \
is, what it does IN THIS CIRCUIT, and how it can fail.
  3. READ visible markings: reference designators (teach the codes when \
audience is student: R=resistor, C=capacitor, D=diode, Q=transistor, U=IC, \
L=inductor, F=fuse, K=relay, T=transformer, CN/J=connector) and IC part \
numbers. When you can read a part number, state what that part is from your \
knowledge (e.g. LM317 = adjustable linear voltage regulator; optocoupler \
PC817 = isolation) — but say clearly when a marking is too blurry to read \
and ask for a closer photo of that area.
  4. For each suspect or safety-relevant part: how to TEST it in place or \
out (multimeter mode, expected reading — e.g. electrolytic cap bulging/ESR, \
diode drop ~0.6 V, fuse continuity, MOSFET gate short) and typical visual \
failure signs (bulged caps, scorch marks, cracked solder joints, corrosion).
  5. Safety: mains capacitors hold charge after power-off — say how to \
discharge safely; note when a board is in the patient-connected isolation \
barrier and must only be replaced, not patched, to keep IEC 60601 isolation.
- For troubleshooting: safety precautions FIRST (electrical isolation, \
patient disconnection, gas/fluid/pressure hazards, capacitor discharge), then \
ordered checks from most-likely/cheapest to least-likely, each with the \
expected result, then when to escalate to the manufacturer. Rank failure \
modes by how common they are in the field.
- Mention relevant standards by name/number (IEC 60601 family, NFPA 99, \
AAMI) where they apply, but do not fabricate clause text.
- Always include a short "Safety" note when the equipment involves patient \
connection, high voltage, stored energy, radiation, lasers, or pressurized gas.
- When reference data (iFixit guides, FDA classification, recalls) appears in \
a <reference_data> block, use it and mention guide titles. Do not invent URLs.
- Be honest about uncertainty. A wrong confident answer can harm a patient.
- VIDEO: when the user attaches a video, watch AND listen. Describe what you \
observe over time (startup sequence, display behavior, error codes appearing, \
mechanical movement, abnormal sounds — clicks, grinding, alarms, relay \
chatter) with timestamps, and use those observations as diagnostic evidence.

## Illustrations
Insert photo markers on their own line: [IMAGE: <2-3 word photo search \
phrase>]. Short, generic, widely photographed phrases only (e.g. \
"peristaltic pump", "SpO2 sensor", "ultrasound transducer", "ATX power \
supply", "trackball control panel") — never model numbers, never more than \
3 words.
- In modes "components" and "board": put ONE marker directly under EVERY \
major component/subsystem you describe (up to 12) — seeing each part is how \
the user learns to recognize it on the real machine.
- In other modes: up to 5 markers where a picture genuinely helps.
Choose phrases for the GENERIC part type, not the specific model (e.g. for \
an ultrasound beamformer use "ultrasound beamformer board" or "electronics \
circuit board", for a monitor's PSU use "switching power supply").

## Conversation
This may be a multi-turn conversation — earlier turns are provided. Build on \
what was already discussed; don't repeat whole sections already given.

## Tone
Clinical and precise, like a senior engineer's bench notes — not a chatbot. \
No emoji. No filler openers ("Great question!", "Alright, let's dive in", \
"my friend"). Start directly with substance. Warmth comes from being \
genuinely useful and clear, not from casual phrasing.

## Output format
Clean markdown, short headings, bullet lists. Practical — you are a mentor \
at the bench, not a textbook.
Then, at the very end, output the line ---FOLLOW-UP--- followed by exactly 3 \
short follow-up questions (one per line, no numbering) the user would most \
benefit from asking next — tuned to their audience level (for students: \
deepen understanding; for technicians/seniors: next diagnostic or related \
failure mode).
"""


class AIKeyMissing(Exception):
    pass


def _gemini_keys() -> list[str]:
    """All env vars starting with GEMINI_API_KEY, in name order."""
    found = sorted(
        (name, value.strip())
        for name, value in os.environ.items()
        if name.startswith("GEMINI_API_KEY") and value.strip()
    )
    return [value for _, value in found]


def _build_user_text(question: str, mode: str, level: str, context: str) -> str:
    text = f"Audience: {level}\nMode: {mode}\n"
    if question.strip():
        text += f"Question: {question.strip()}\n"
    else:
        text += "No specific question — give the standard answer for this mode.\n"
    if context:
        text += f"\n<reference_data>\n{context}\n</reference_data>\n"
    text += (
        "\nRemember: end with the ---FOLLOW-UP--- line followed by exactly "
        "3 follow-up questions.\n"
    )
    return text


def _split_followups(raw: str) -> tuple[str, list[str]]:
    """Separate the answer body from the trailing follow-up questions."""
    if FOLLOWUP_SEPARATOR not in raw:
        return raw.strip(), []
    body, _, tail = raw.rpartition(FOLLOWUP_SEPARATOR)
    followups = [
        line.strip().lstrip("-•*0123456789. ").strip()
        for line in tail.strip().splitlines()
        if line.strip()
    ]
    return body.strip(), [q for q in followups if q][:3]


def analyze(
    *,
    question: str,
    mode: str,
    level: str = "technician",
    media: list[tuple[bytes, str]] | None = None,
    history: list[dict] | None = None,
    context: str = "",
) -> dict:
    """Run the analysis. Returns {"answer": markdown, "followups": [str, ...]}.

    ``media`` — list of (bytes, mime_type) pairs (images and/or video),
    processed in memory only. Video requires Gemini.
    ``history`` — earlier turns: [{"role": "user"|"assistant", "text": str}].
    """
    from . import images as image_service

    text = _build_user_text(question, mode, level, context)
    media = media or []
    history = history or []

    gemini_keys = _gemini_keys()
    if gemini_keys:
        raw = _analyze_gemini(gemini_keys, text, media, history)
    elif os.getenv("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_AUTH_TOKEN"):
        raw = _analyze_claude(text, media, history)
    else:
        raise AIKeyMissing(
            "No AI key configured. Add GEMINI_API_KEY (free at aistudio.google.com) "
            "or ANTHROPIC_API_KEY to your .env file."
        )

    answer, followups = _split_followups(raw)
    # Replace [IMAGE: ...] markers with real photos (Wikimedia/Openverse).
    answer = image_service.illustrate(answer)
    return {"answer": answer, "followups": followups}


def _analyze_gemini(
    keys: list[str],
    text: str,
    media: list[tuple[bytes, str]],
    history: list[dict],
) -> str:
    from google import genai
    from google.genai import types

    env_model = os.getenv("GEMINI_MODEL", "").strip()
    models = [env_model] if env_model else GEMINI_MODEL_ORDER

    contents = []
    for turn in history:
        role = "user" if turn.get("role") == "user" else "model"
        contents.append(types.Content(
            role=role,
            parts=[types.Part.from_text(text=turn.get("text", ""))],
        ))

    parts = [
        types.Part.from_bytes(data=blob, mime_type=mime)
        for blob, mime in media
    ]
    parts.append(types.Part.from_text(text=text))
    contents.append(types.Content(role="user", parts=parts))

    last_error: Exception | None = None
    # Accuracy first: strongest model across all keys, then the next model.
    for model in models:
        for key in keys:
            try:
                # 120s cap per attempt — a stall rotates instead of hanging.
                client = genai.Client(
                    api_key=key,
                    http_options=types.HttpOptions(timeout=120_000),
                )
                response = client.models.generate_content(
                    model=model,
                    contents=contents,
                    # Generous cap: 2.5-pro spends output budget on internal
                    # reasoning; too low a cap truncates the follow-up block.
                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM_PROMPT,
                        max_output_tokens=16000,
                    ),
                )
                if response.text:
                    return response.text
                last_error = RuntimeError("Gemini returned an empty response.")
            except Exception as exc:
                last_error = exc
    raise last_error or RuntimeError("All Gemini keys failed.")


def _analyze_claude(
    text: str,
    media: list[tuple[bytes, str]],
    history: list[dict],
) -> str:
    import base64

    import anthropic

    client = anthropic.Anthropic()

    messages = []
    for turn in history:
        role = "user" if turn.get("role") == "user" else "assistant"
        messages.append({"role": role, "content": turn.get("text", "")})

    user_parts = []
    for blob, mime in media:
        if not mime.startswith("image/"):
            continue  # video is Gemini-only; the view guards this
        user_parts.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": mime,
                "data": base64.standard_b64encode(blob).decode("utf-8"),
            },
        })
    user_parts.append({"type": "text", "text": text})
    messages.append({"role": "user", "content": user_parts})

    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=8000,
        system=[{
            "type": "text",
            "text": SYSTEM_PROMPT,
            "cache_control": {"type": "ephemeral"},
        }],
        messages=messages,
    )
    return "".join(b.text for b in response.content if b.type == "text")


def build_context(equipment_name: str) -> str:
    """Gather grounding data from iFixit + openFDA for the prompt."""
    from . import ifixit, openfda

    if not equipment_name.strip():
        return ""

    lines = []
    guides = ifixit.search_guides(equipment_name, limit=5)
    if guides:
        lines.append("iFixit repair guides found:")
        for g in guides:
            lines.append(f"- {g['title']} ({g['url']})")

    classifications = openfda.classify_device(equipment_name, limit=3)
    if classifications:
        lines.append("\nFDA device classification:")
        for c in classifications:
            lines.append(
                f"- {c['device_name']} — Class {c['device_class']}, "
                f"{c['medical_specialty']}. {c['definition'][:250]}"
            )

    recalls = openfda.recent_recalls(equipment_name, limit=3)
    if recalls:
        lines.append("\nRecent FDA recalls:")
        for r in recalls:
            lines.append(f"- {r['product'][:100]}: {r['reason'][:150]} ({r['firm']})")

    return "\n".join(lines)
