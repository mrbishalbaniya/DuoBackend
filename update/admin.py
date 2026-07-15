import logging
from urllib.parse import urlencode

from django.contrib import admin, messages
from django.db import DatabaseError, ProgrammingError
from django.http import HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from update.forms import AppVersionAdminForm
from update.models import AppVersion
from update.services.admin_helpers import resolve_apk_url
from update.services.bootstrap import seed_initial_versions, update_table_exists
from update.services.github import (
    GithubReleaseError,
    fetch_latest_github_release,
    github_latest_apk_url,
    github_releases_page_url,
    github_repo,
    sync_app_version_from_github,
)
from update.services.storage import save_apk_file
from update.services.version import activate_version, compute_sha256, get_active_version, publish_version, rollback_version

logger = logging.getLogger("update")


@admin.register(AppVersion)
class AppVersionAdmin(admin.ModelAdmin):
    form = AppVersionAdminForm
    change_list_template = "admin/update/appversion/change_list.html"
    list_display = (
        "version",
        "build_number",
        "platform",
        "channel",
        "status_badges",
        "display_file_size",
        "download_count",
        "github_links",
        "published_at",
    )
    list_filter = ("platform", "channel", "is_active", "is_published", "force_update", "emergency_update")
    search_fields = ("version", "release_title", "apk_url", "checksum_sha256", "minimum_version")
    ordering = ("-build_number", "-published_at", "-created_at")
    list_per_page = 25
    readonly_fields = (
        "download_count",
        "display_file_size",
        "checksum_sha256",
        "file_size_bytes",
        "published_at",
        "created_at",
        "updated_at",
        "apk_preview",
        "github_links",
    )
    fieldsets = (
        (
            "Release",
            {
                "fields": (
                    "version",
                    "build_number",
                    "platform",
                    "channel",
                    "release_title",
                    "release_notes_text",
                    "minimum_version",
                ),
                "description": (
                    "Release Title and Release Notes are shown to users in the app. "
                    "Prefer Sync from GitHub for version/build/APK accuracy. "
                    "Never paste raw GitHub release bodies into Release Notes."
                ),
            },
        ),
        (
            "Distribution",
            {
                "fields": (
                    "apk_file",
                    "apk_url",
                    "apk_preview",
                    "github_links",
                    "file_size_bytes",
                    "display_file_size",
                    "checksum_sha256",
                    "download_count",
                ),
                "description": (
                    "apk_url can point at the GitHub release asset "
                    "(same download the mobile app uses)."
                ),
            },
        ),
        (
            "Policy",
            {
                "fields": (
                    "soft_update",
                    "force_update",
                    "emergency_update",
                    "is_published",
                    "is_active",
                    "published_at",
                )
            },
        ),
        ("Audit", {"fields": ("created_at", "updated_at")}),
    )
    actions = (
        "publish_selected",
        "activate_selected",
        "rollback_selected",
        "deactivate_selected",
        "sync_selected_from_github",
    )

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                "sync-github/",
                self.admin_site.admin_view(self.sync_from_github_view),
                name="update_appversion_sync_github",
            ),
        ]
        return custom + urls

    def get_search_results(self, request, queryset, search_term):
        queryset, use_distinct = super().get_search_results(request, queryset, search_term)
        if not search_term:
            return queryset, use_distinct

        stripped = search_term.strip()
        if stripped.isdigit():
            queryset = queryset | self.model.objects.filter(build_number=int(stripped))
            use_distinct = True
        return queryset, use_distinct

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        if not update_table_exists():
            logger.error("AppVersion admin changelist blocked: update_appversion table is missing")
            self.message_user(
                request,
                "Update service tables are missing. Run: python manage.py ensure_update_service",
                level=messages.ERROR,
            )
            context = {
                **self.admin_site.each_context(request),
                "title": "App versions unavailable",
                "opts": self.model._meta,
                "app_label": self.model._meta.app_label,
            }
            return TemplateResponse(request, "admin/update/db_not_ready.html", context)

        try:
            if not AppVersion.objects.exists():
                seed_initial_versions()
        except (DatabaseError, ProgrammingError):
            logger.exception("Failed to seed AppVersion rows for admin changelist")

        extra_context.update(self._github_changelist_context())

        try:
            return super().changelist_view(request, extra_context=extra_context)
        except (DatabaseError, ProgrammingError):
            logger.exception("AppVersion admin changelist database error")
            self.message_user(
                request,
                "Could not load app versions due to a database error. Check server logs.",
                level=messages.ERROR,
            )
            context = {
                **self.admin_site.each_context(request),
                "title": "App versions unavailable",
                "opts": self.model._meta,
                "app_label": self.model._meta.app_label,
            }
            return TemplateResponse(request, "admin/update/db_not_ready.html", context)

    def _github_changelist_context(self) -> dict:
        from types import SimpleNamespace

        context: dict = {
            "github_repo": github_repo(),
            "github_releases_url": github_releases_page_url(),
            "github_latest_apk_url": github_latest_apk_url(),
            "github_release": None,
            "github_error": None,
            "github_matches_active": False,
            "github_file_size_label": "",
            "active_version": None,
        }
        try:
            context["active_version"] = get_active_version(platform=AppVersion.PLATFORM_ANDROID)
        except Exception:
            logger.exception("Failed loading active AppVersion for GitHub panel")

        try:
            release = fetch_latest_github_release()
            published = (
                release.published_at.strftime("%b %d, %Y · %H:%M UTC")
                if release.published_at is not None
                else "—"
            )
            context["github_release"] = SimpleNamespace(
                tag=release.tag,
                version=release.version,
                build_number=release.build_number,
                release_title=release.release_title,
                html_url=release.html_url,
                file_size_bytes=release.file_size_bytes,
                published_at=published,
            )
            if release.file_size_bytes > 0:
                context["github_file_size_label"] = f"{release.file_size_bytes / (1024 * 1024):.1f} MB"
            active = context["active_version"]
            if active is not None:
                context["github_matches_active"] = (
                    active.version == release.version and active.build_number == release.build_number
                )
        except GithubReleaseError as exc:
            context["github_error"] = str(exc)
        except Exception as exc:
            logger.exception("Unexpected GitHub panel failure")
            context["github_error"] = str(exc)
        return context

    def sync_from_github_view(self, request):
        if request.method not in {"GET", "POST"}:
            return HttpResponseRedirect(reverse("admin:update_appversion_changelist"))

        try:
            row, release, created = sync_app_version_from_github(activate=True, publish=True)
        except GithubReleaseError as exc:
            self.message_user(request, f"GitHub sync failed: {exc}", level=messages.ERROR)
            return HttpResponseRedirect(reverse("admin:update_appversion_changelist"))
        except Exception as exc:
            logger.exception("GitHub sync crashed")
            self.message_user(request, f"GitHub sync failed: {exc}", level=messages.ERROR)
            return HttpResponseRedirect(reverse("admin:update_appversion_changelist"))

        verb = "Created" if created else "Updated"
        self.message_user(
            request,
            (
                f"{verb} OTA {row.version}+{row.build_number} from GitHub tag {release.tag}. "
                f"APK: {release.file_size_bytes // (1024 * 1024)} MB."
            ),
            level=messages.SUCCESS,
        )
        query = urlencode({"q": str(row.build_number)})
        return HttpResponseRedirect(f"{reverse('admin:update_appversion_changelist')}?{query}")

    def get_queryset(self, request):
        try:
            return super().get_queryset(request)
        except (DatabaseError, ProgrammingError):
            logger.exception("AppVersionAdmin.get_queryset failed")
            return self.model.objects.none()

    @admin.display(description="Status", ordering="is_active")
    def status_badges(self, obj: AppVersion) -> str:
        if obj is None:
            return "—"
        badges: list[str] = []
        try:
            if obj.is_active:
                badges.append('<span style="color:#16a34a;font-weight:700;">ACTIVE</span>')
            if obj.is_published:
                badges.append('<span style="color:#2563eb;">Published</span>')
            if obj.force_update:
                badges.append('<span style="color:#dc2626;">Force</span>')
            if obj.emergency_update:
                badges.append('<span style="color:#b91c1c;">Emergency</span>')
        except Exception:
            logger.exception("status_badges failed for AppVersion id=%s", getattr(obj, "pk", None))
            return "—"
        if not badges:
            return "—"
        return mark_safe(" · ".join(badges))

    @admin.display(description="File size", ordering="file_size_bytes")
    def display_file_size(self, obj: AppVersion) -> str:
        if obj is None:
            return "Unknown"
        try:
            return obj.file_size_label
        except Exception:
            logger.exception("display_file_size failed for AppVersion id=%s", getattr(obj, "pk", None))
            return "Unknown"

    @admin.display(description="APK")
    def apk_preview(self, obj: AppVersion) -> str:
        if obj is None:
            return "—"
        url = resolve_apk_url(obj)
        if not url:
            return "—"
        return format_html('<a href="{}" target="_blank" rel="noopener">Download APK</a>', url)

    @admin.display(description="GitHub")
    def github_links(self, obj: AppVersion) -> str:
        if obj is None:
            return "—"
        parts: list[str] = [
            format_html(
                '<a href="{}" target="_blank" rel="noopener">Releases</a>',
                github_releases_page_url(),
            )
        ]
        url = resolve_apk_url(obj)
        if url and "github.com" in url:
            parts.append(format_html('<a href="{}" target="_blank" rel="noopener">APK</a>', url))
        else:
            parts.append(
                format_html(
                    '<a href="{}" target="_blank" rel="noopener">Latest APK</a>',
                    github_latest_apk_url(),
                )
            )
        tag_guess = f"v{obj.version}-build.{obj.build_number}"
        parts.append(
            format_html(
                '<a href="https://github.com/{}/releases/tag/{}" target="_blank" rel="noopener">Tag</a>',
                github_repo(),
                tag_guess,
            )
        )
        return mark_safe(" · ".join(parts))

    def save_model(self, request, obj, form, change):
        uploaded = request.FILES.get("apk_file")
        if uploaded is not None:
            try:
                checksum, size = compute_sha256(uploaded)
                saved_path, public_url = save_apk_file(
                    version=obj.version or "0.0.0",
                    build_number=obj.build_number or 1,
                    uploaded_file=uploaded,
                )
                obj.apk_file.name = saved_path
                if not (obj.apk_url or "").strip():
                    obj.apk_url = public_url
                obj.checksum_sha256 = checksum
                obj.file_size_bytes = size
            except Exception:
                logger.exception("Failed to process APK upload for AppVersion")
                self.message_user(
                    request,
                    "APK upload failed. Check storage configuration and try again.",
                    level=messages.ERROR,
                )
                raise

        if isinstance(obj.release_notes, str):
            from update.services.version import parse_release_notes

            obj.release_notes = parse_release_notes(obj.release_notes)
        elif obj.release_notes is None:
            obj.release_notes = []

        super().save_model(request, obj, form, change)

    @admin.action(description="Publish selected releases")
    def publish_selected(self, request, queryset):
        count = 0
        for version in queryset:
            try:
                publish_version(version, activate=False)
                count += 1
            except Exception:
                logger.exception("publish_selected failed for id=%s", version.pk)
        self.message_user(request, f"Published {count} release(s).", messages.SUCCESS)

    @admin.action(description="Activate selected release (per platform/channel)")
    def activate_selected(self, request, queryset):
        count = 0
        for version in queryset:
            try:
                activate_version(version)
                count += 1
            except Exception:
                logger.exception("activate_selected failed for id=%s", version.pk)
        self.message_user(request, f"Activated {count} release(s).", messages.SUCCESS)

    @admin.action(description="Deactivate selected releases")
    def deactivate_selected(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f"Deactivated {updated} release(s).", messages.WARNING)

    @admin.action(description="Rollback to previous published build")
    def rollback_selected(self, request, queryset):
        rolled = 0
        seen: set[tuple[str, str]] = set()
        for version in queryset:
            key = (version.platform, version.channel)
            if key in seen:
                continue
            seen.add(key)
            try:
                previous = rollback_version(platform=version.platform, channel=version.channel)
                if previous is not None:
                    rolled += 1
            except Exception:
                logger.exception(
                    "rollback_selected failed for platform=%s channel=%s",
                    version.platform,
                    version.channel,
                )
        if rolled:
            self.message_user(request, f"Rolled back {rolled} channel(s).", messages.SUCCESS)
        else:
            self.message_user(request, "No previous release found to roll back to.", messages.ERROR)

    @admin.action(description="Sync latest from GitHub (ignore selection)")
    def sync_selected_from_github(self, request, queryset):
        try:
            row, release, created = sync_app_version_from_github(activate=True, publish=True)
        except GithubReleaseError as exc:
            self.message_user(request, f"GitHub sync failed: {exc}", level=messages.ERROR)
            return
        except Exception as exc:
            logger.exception("sync_selected_from_github failed")
            self.message_user(request, f"GitHub sync failed: {exc}", level=messages.ERROR)
            return
        verb = "Created" if created else "Updated"
        self.message_user(
            request,
            f"{verb} {row.version}+{row.build_number} from {release.tag}.",
            level=messages.SUCCESS,
        )
