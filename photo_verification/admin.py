import json

from django.contrib import admin, messages
from django.utils import timezone
from django.utils.html import format_html, format_html_join

from photo_verification import constants as photo_constants

from photo_verification.models import FaceEmbedding, PhotoAnalysis, UserVerification
from photo_verification.services.verification_engine import VerificationEngine


@admin.register(PhotoAnalysis)
class PhotoAnalysisAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "status",
        "quality_score",
        "face_count",
        "ai_generated_probability",
        "duplicate_probability",
        "is_primary",
        "created_at",
    )
    list_filter = ("status", "face_detected", "resolution_passed", "is_primary")
    search_fields = ("user__username", "user__email", "image_url")
    readonly_fields = (
        "user",
        "image_url",
        "image_hash",
        "embedding",
        "face_detected",
        "face_count",
        "face_centered",
        "blur_score",
        "brightness_score",
        "resolution_passed",
        "image_width",
        "image_height",
        "quality_score",
        "ai_generated_probability",
        "duplicate_probability",
        "status",
        "warnings",
        "rejection_reasons",
        "created_at",
        "photo_summary",
        "photo_checks",
        "technical_details",
    )
    fieldsets = (
        (None, {"fields": ("photo_summary",)}),
        ("Checks", {"fields": ("photo_checks",)}),
        ("Details", {"fields": ("user", "is_primary", "image_url", "created_at", "technical_details")}),
    )
    ordering = ("-created_at",)

    @admin.display(description="Result")
    def photo_summary(self, obj: PhotoAnalysis):
        return _render_photo_summary(obj)

    @admin.display(description="What was checked")
    def photo_checks(self, obj: PhotoAnalysis):
        return _render_photo_checks(obj)

    @admin.display(description="Technical details")
    def technical_details(self, obj: PhotoAnalysis):
        raw = {
            "image_hash": obj.image_hash,
            "blur_score (Laplacian variance)": obj.blur_score,
            "brightness_score (0-255)": obj.brightness_score,
            "ai_generated_probability": obj.ai_generated_probability,
            "duplicate_probability": obj.duplicate_probability,
            "embedding": obj.embedding,
        }
        return format_html(
            '<details><summary style="cursor:pointer;opacity:.8">Show raw analysis values '
            "(hash, raw scores and face vector, for debugging)</summary>"
            '<pre style="white-space:pre-wrap;max-height:420px;overflow:auto;font-size:12px;'
            'margin-top:8px;padding:12px;border-radius:8px;background:rgba(127,127,127,.08)">{}</pre></details>',
            json.dumps(raw, indent=2, default=str),
        )


@admin.register(FaceEmbedding)
class FaceEmbeddingAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "is_primary", "face_count", "quality_score", "created_at")
    list_filter = ("is_primary",)
    search_fields = ("user__username", "photo_url")
    readonly_fields = ("embedding_vector", "created_at")


@admin.register(UserVerification)
class UserVerificationAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "verification_status",
        "similarity_score",
        "liveness_score",
        "fraud_probability",
        "verified_at",
        "created_at",
    )
    list_filter = ("verification_status",)
    search_fields = ("user__username", "user__email")
    readonly_fields = (
        "session_token",
        "similarity_score",
        "liveness_score",
        "fraud_probability",
        "liveness_data",
        "liveness_summary",
        "liveness_raw",
        "verified_at",
        "created_at",
        "updated_at",
        "profile_preview",
        "selfie_preview",
    )
    fieldsets = (
        (None, {"fields": ("user", "verification_status", "review_notes", "rejection_reasons")}),
        (
            "Scores",
            {"fields": ("similarity_score", "liveness_score", "fraud_probability")},
        ),
        (
            "Images",
            {"fields": ("profile_photo_url", "profile_preview", "selfie_photo_url", "selfie_preview")},
        ),
        ("Liveness", {"fields": ("liveness_summary", "liveness_raw")}),
        ("Meta", {"fields": ("session_token", "expires_at", "verified_at", "created_at", "updated_at")}),
    )
    actions = ["approve_verification", "reject_verification", "request_retake"]

    @admin.display(description="Liveness check")
    def liveness_summary(self, obj: UserVerification):
        return _render_liveness_summary(obj.liveness_data or {})

    @admin.display(description="Technical details")
    def liveness_raw(self, obj: UserVerification):
        data = obj.liveness_data or {}
        if not data:
            return "—"
        return format_html(
            '<details><summary style="cursor:pointer;opacity:.8">Show raw liveness data '
            '(face vectors and camera baselines, for debugging)</summary>'
            '<pre style="white-space:pre-wrap;max-height:420px;overflow:auto;font-size:12px;'
            'margin-top:8px;padding:12px;border-radius:8px;background:rgba(127,127,127,.08)">{}</pre></details>',
            json.dumps(data, indent=2, default=str),
        )

    @admin.display(description="Profile")
    def profile_preview(self, obj: UserVerification):
        if not obj.profile_photo_url:
            return "—"
        return format_html('<img src="{}" style="max-height:120px;border-radius:8px;" />', obj.profile_photo_url)

    @admin.display(description="Selfie")
    def selfie_preview(self, obj: UserVerification):
        if not obj.selfie_photo_url:
            return "—"
        return format_html('<img src="{}" style="max-height:120px;border-radius:8px;" />', obj.selfie_photo_url)

    @admin.action(description="Approve — award verified badge")
    def approve_verification(self, request, queryset):
        for session in queryset:
            VerificationEngine.admin_approve(session, notes="Approved by admin")
        self.message_user(request, f"Approved {queryset.count()} verification(s).", messages.SUCCESS)

    @admin.action(description="Reject verification")
    def reject_verification(self, request, queryset):
        for session in queryset:
            VerificationEngine.admin_reject(session, notes="Rejected by admin")
        self.message_user(request, f"Rejected {queryset.count()} verification(s).", messages.WARNING)

    @admin.action(description="Request retake (reset to pending)")
    def request_retake(self, request, queryset):
        queryset.update(
            verification_status="PENDING",
            selfie_photo_url="",
            similarity_score=0,
            liveness_score=0,
            liveness_data={},
            rejection_reasons=["Please retake verification."],
        )
        self.message_user(request, "Marked for retake.", messages.INFO)


STEP_LABELS = {
    "blink": "Blink",
    "head_right": "Turn head right",
    "head_left": "Turn head left",
    "smile": "Smile",
    "nod": "Nod",
    "open_mouth": "Open mouth",
}


def _parse_dt(value):
    from django.utils.dateparse import parse_datetime

    try:
        return parse_datetime(str(value)) if value else None
    except (TypeError, ValueError):
        return None


def _render_liveness_summary(data: dict):
    """Turn the raw liveness JSON into a reviewer-friendly step checklist."""
    if not data:
        return "No liveness check recorded yet."

    steps = [s for s in data.get("_steps", []) if isinstance(s, str)]
    # Include any result keys that are not in the planned step list.
    for key, value in data.items():
        if not key.startswith("_") and isinstance(value, dict) and "passed" in value and key not in steps:
            steps.append(key)

    badge = (
        '<span style="display:inline-block;padding:2px 10px;border-radius:999px;font-weight:700;'
        'font-size:12px;color:{};background:{}">{}</span>'
    )
    rows = []
    passed_count = 0
    for step in steps:
        result = data.get(step)
        if isinstance(result, dict):
            ok = bool(result.get("passed"))
            passed_count += ok
            status = format_html(badge, "#15803d" if ok else "#b91c1c",
                                 "rgba(34,197,94,.15)" if ok else "rgba(239,68,68,.15)",
                                 "Passed" if ok else "Failed")
            try:
                score = f"{float(result.get('score', 0)) * 100:.0f}%"
            except (TypeError, ValueError):
                score = "—"
            detail = result.get("detail") or "—"
        else:
            status = format_html(badge, "#6b7280", "rgba(107,114,128,.15)", "Not reached")
            score, detail = "—", "The user stopped before this step."
        rows.append((STEP_LABELS.get(step, step.replace("_", " ").capitalize()), status, score, detail))

    started = _parse_dt(data.get("_started_at"))
    last = _parse_dt(data.get("_last_frame_at"))
    frames = data.get("_frames") or []
    detectors = sorted({f.get("detector") for f in frames if isinstance(f, dict) and f.get("detector")})

    facts = [("Steps passed", f"{passed_count} of {len(steps)}" if steps else "—")]
    if started:
        facts.append(("Started", timezone.localtime(started).strftime("%Y-%m-%d %H:%M:%S")))
    if started and last:
        secs = max(0, int((last - started).total_seconds()))
        facts.append(("Duration", f"{secs // 60} min {secs % 60} s" if secs >= 60 else f"{secs} s"))
    facts.append(("Frames captured", str(len(frames))))
    if detectors:
        facts.append(("Face detector", ", ".join(detectors)))

    cell = 'style="padding:8px 12px;border-bottom:1px solid rgba(127,127,127,.2);text-align:left;vertical-align:top"'
    head = 'style="padding:8px 12px;border-bottom:1px solid rgba(127,127,127,.35);text-align:left;font-size:12px;text-transform:uppercase;letter-spacing:.05em;opacity:.7"'
    facts_html = format_html_join(
        "", '<div style="min-width:130px"><div style="font-size:12px;opacity:.7">{}</div><div style="font-weight:700;font-size:15px">{}</div></div>', facts
    )
    rows_html = format_html_join(
        "", "<tr><td " + cell + "><strong>{}</strong></td><td " + cell + ">{}</td><td " + cell + ">{}</td><td " + cell + ">{}</td></tr>", rows
    )
    return format_html(
        '<div style="display:flex;flex-wrap:wrap;gap:20px;margin-bottom:16px">{}</div>'
        '<table style="width:100%;border-collapse:collapse">'
        "<thead><tr><th " + head + ">Step</th><th " + head + ">Result</th><th " + head + ">Confidence</th><th " + head + ">What happened</th></tr></thead>"
        "<tbody>{}</tbody></table>",
        facts_html,
        rows_html or format_html("<tr><td colspan='4' " + cell + ">No steps recorded.</td></tr>"),
    )


_BADGE = (
    '<span style="display:inline-block;padding:2px 10px;border-radius:999px;font-weight:700;'
    'font-size:12px;color:{};background:{}">{}</span>'
)
_TONES = {
    "ok": ("#15803d", "rgba(34,197,94,.15)"),
    "warn": ("#b45309", "rgba(245,158,11,.18)"),
    "fail": ("#b91c1c", "rgba(239,68,68,.15)"),
    "info": ("#6b7280", "rgba(107,114,128,.15)"),
}
_CELL = 'style="padding:8px 12px;border-bottom:1px solid rgba(127,127,127,.2);text-align:left;vertical-align:top"'
_HEAD = (
    'style="padding:8px 12px;border-bottom:1px solid rgba(127,127,127,.35);text-align:left;'
    'font-size:12px;text-transform:uppercase;letter-spacing:.05em;opacity:.7"'
)


def _badge(tone: str, text: str):
    color, bg = _TONES[tone]
    return format_html(_BADGE, color, bg, text)


def _pct(value) -> str:
    try:
        return f"{float(value) * 100:.0f}%"
    except (TypeError, ValueError):
        return "—"


def _render_photo_summary(obj):
    """Verdict, quality score and the issues list, next to the photo itself."""
    status = (obj.status or "").upper()
    tone = {"APPROVED": "ok", "WARNING": "warn", "REJECTED": "fail"}.get(status, "info")
    meaning = {
        "APPROVED": "The photo passed every automatic check.",
        "WARNING": "The photo was accepted, but some checks raised concerns worth a look.",
        "REJECTED": "The photo failed at least one automatic check and was not accepted.",
    }.get(status, "")
    issues = [("Rejected", r) for r in (obj.rejection_reasons or [])]
    issues += [("Warning", w) for w in (obj.warnings or [])]
    if issues:
        items = format_html_join(
            "",
            '<li style="margin:4px 0">{} {}</li>',
            ((_badge("fail" if kind == "Rejected" else "warn", kind), text) for kind, text in issues),
        )
        issues_html = format_html('<ul style="margin:6px 0 0;padding-left:18px">{}</ul>', items)
    else:
        issues_html = format_html('<p style="margin:6px 0 0;opacity:.7">{}</p>', "No issues found.")

    image = ""
    if obj.image_url:
        image = format_html(
            '<a href="{0}" target="_blank" rel="noopener"><img src="{0}" alt="Analysed photo" '
            'style="max-height:220px;max-width:180px;border-radius:10px;object-fit:cover;display:block"></a>',
            obj.image_url,
        )
    return format_html(
        '<div style="display:flex;gap:24px;flex-wrap:wrap;align-items:flex-start">{}'
        '<div style="flex:1;min-width:240px">'
        '<div style="display:flex;gap:12px;align-items:center;flex-wrap:wrap">{}'
        '<span style="font-size:15px">Quality score <strong style="font-size:22px">{}</strong> / 100</span></div>'
        '<p style="margin:10px 0 6px;opacity:.85">{}</p>{}</div></div>',
        image,
        _badge(tone, status.title() or "Unknown"),
        obj.quality_score,
        meaning,
        issues_html,
    )


def _render_photo_checks(obj):
    """One row per automatic check, judged with the pipeline's own thresholds."""
    c = photo_constants
    rows = []

    found = bool(obj.face_detected)
    rows.append(("Face found", "Yes" if found else "No",
                 _badge("ok" if found else "fail", "OK" if found else "Fail"),
                 "A profile photo must show a face."))

    if obj.face_count == 1:
        people = ("ok", "OK", "Exactly one person, so it is clear who the profile belongs to.")
    elif obj.face_count == 0:
        people = ("fail", "Fail", "No face could be counted.")
    else:
        people = ("warn", "Warning", "Several people appear, so it is unclear who the profile belongs to.")
    rows.append(("People in photo", str(obj.face_count), _badge(people[0], people[1]), people[2]))

    centered = bool(obj.face_centered)
    rows.append(("Face centered", "Yes" if centered else "No",
                 _badge("ok" if centered else "warn", "OK" if centered else "Warning"),
                 "The face should sit near the middle of the frame."))

    blur = obj.blur_score or 0
    if blur < c.BLUR_REJECT_THRESHOLD:
        sharp = ("fail", "Fail", "Very blurry")
    elif blur < c.BLUR_WARNING_THRESHOLD:
        sharp = ("warn", "Warning", "Slightly soft")
    else:
        sharp = ("ok", "OK", "Sharp")
    rows.append(("Sharpness", sharp[2], _badge(sharp[0], sharp[1]),
                 f"Scores below {c.BLUR_REJECT_THRESHOLD:.0f} are rejected and below "
                 f"{c.BLUR_WARNING_THRESHOLD:.0f} are flagged. This photo scored {blur:.0f}."))

    light = obj.brightness_score or 0
    if light < c.BRIGHTNESS_LOW_WARNING:
        lit = ("warn", "Warning", "Too dark")
    elif light > c.BRIGHTNESS_HIGH_WARNING:
        lit = ("warn", "Warning", "Too bright")
    else:
        lit = ("ok", "OK", "Good lighting")
    rows.append(("Lighting", lit[2], _badge(lit[0], lit[1]),
                 f"Average brightness should be between {c.BRIGHTNESS_LOW_WARNING:.0f} and "
                 f"{c.BRIGHTNESS_HIGH_WARNING:.0f} on a 0 to 255 scale. This photo is {light:.0f}."))

    res_ok = bool(obj.resolution_passed)
    rows.append(("Resolution", f"{obj.image_width} × {obj.image_height} px",
                 _badge("ok" if res_ok else "fail", "OK" if res_ok else "Fail"),
                 f"The minimum is {c.MIN_IMAGE_WIDTH} × {c.MIN_IMAGE_HEIGHT} px."))

    ai = obj.ai_generated_probability or 0
    if ai >= c.AI_REJECT_THRESHOLD:
        ai_res = ("fail", "Fail")
    elif ai >= c.AI_FLAG_THRESHOLD:
        ai_res = ("warn", "Warning")
    else:
        ai_res = ("ok", "OK")
    rows.append(("Looks AI-generated", f"{_pct(ai)} likely", _badge(*ai_res),
                 f"Flagged from {_pct(c.AI_FLAG_THRESHOLD)} and rejected from {_pct(c.AI_REJECT_THRESHOLD)}."))

    dup = obj.duplicate_probability or 0
    if dup >= c.DUPLICATE_REJECT_THRESHOLD:
        dup_res = ("fail", "Fail")
    elif dup >= c.DUPLICATE_FLAG_THRESHOLD:
        dup_res = ("warn", "Warning")
    else:
        dup_res = ("ok", "OK")
    rows.append(("Matches another photo", f"{_pct(dup)} similar", _badge(*dup_res),
                 "Similarity to photos already on the platform. Flagged from "
                 f"{_pct(c.DUPLICATE_FLAG_THRESHOLD)} and rejected from {_pct(c.DUPLICATE_REJECT_THRESHOLD)}."))

    body = format_html_join(
        "",
        "<tr><td " + _CELL + "><strong>{}</strong></td><td " + _CELL + ">{}</td><td "
        + _CELL + ">{}</td><td " + _CELL + ">{}</td></tr>",
        rows,
    )
    return format_html(
        '<table style="width:100%;border-collapse:collapse"><thead><tr>'
        "<th " + _HEAD + ">Check</th><th " + _HEAD + ">This photo</th><th " + _HEAD
        + ">Result</th><th " + _HEAD + ">What it means</th></tr></thead><tbody>{}</tbody></table>",
        body,
    )
