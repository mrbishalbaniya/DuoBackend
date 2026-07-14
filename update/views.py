import logging

from django.db import DatabaseError
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from update.models import AppVersion
from update.permissions import OtaPublishTokenPermission
from update.serializers import (
    AppVersionHistorySerializer,
    AppVersionPublicSerializer,
    AppVersionPublishSerializer,
)
from update.services.bootstrap import ensure_update_database, update_table_exists
from update.services.storage import save_apk_file
from update.services.version import (
    compute_sha256,
    get_active_version,
    publish_version,
    update_blocked,
    update_required,
    version_payload,
)

logger = logging.getLogger("update")

UPDATE_DB_NOT_READY_DETAIL = (
    "Update service is temporarily unavailable. Please try again later."
)
UPDATE_DB_NOT_READY_ADMIN = "Run: python manage.py migrate update && python manage.py ensure_update_service"


def _database_not_ready_response(*, view_name: str):
    logger.error(
        "%s blocked: update_appversion table missing (table_exists=%s)",
        view_name,
        update_table_exists(),
    )
    return Response(
        {
            "detail": UPDATE_DB_NOT_READY_DETAIL,
            "code": "update_db_not_ready",
            "admin_hint": UPDATE_DB_NOT_READY_ADMIN,
        },
        status=status.HTTP_503_SERVICE_UNAVAILABLE,
    )


def _guard_update_database(view_name: str):
    if ensure_update_database(apply_migrations=False):
        return None
    return _database_not_ready_response(view_name=view_name)


@extend_schema(tags=["App Updates"])
class AppVersionCheckView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        blocked = _guard_update_database("AppVersionCheckView")
        if blocked is not None:
            return blocked

        try:
            return self._get(request)
        except DatabaseError:
            logger.exception("DatabaseError in AppVersionCheckView")
            return _database_not_ready_response(view_name="AppVersionCheckView")

    def _get(self, request):
        platform = (request.query_params.get("platform") or AppVersion.PLATFORM_ANDROID).strip().lower()
        channel = (request.query_params.get("channel") or AppVersion.CHANNEL_STABLE).strip().lower()
        installed_version = (request.query_params.get("installed_version") or "0.0.0").strip()
        installed_build = int(request.query_params.get("build_number") or 0)

        logger.info(
            "version check platform=%s channel=%s installed=%s+%s",
            platform,
            channel,
            installed_version,
            installed_build,
        )

        latest = get_active_version(platform=platform, channel=channel)
        if latest is None:
            logger.info("No active AppVersion for platform=%s channel=%s — returning up-to-date payload", platform, channel)
            payload = {
                "latest_version": installed_version,
                "minimum_version": installed_version,
                "build_number": installed_build,
                "apk_url": "",
                "title": "",
                "release_title": "",
                "release_notes": [],
                "force_update": False,
                "soft_update": True,
                "emergency_update": False,
                "mandatory": False,
                "file_size": "0 B",
                "size": "0 B",
                "file_size_bytes": 0,
                "checksum_sha256": "",
                "published_at": None,
                "channel": channel,
                "platform": platform,
                "version": installed_version,
                "build": installed_build,
                "update_available": False,
                "update_blocked": False,
            }
            serializer = AppVersionPublicSerializer(instance=payload)
            return Response(serializer.data)

        payload = version_payload(latest, request=request)
        payload["id"] = latest.id
        payload["update_available"] = update_required(
            installed_version=installed_version,
            installed_build=installed_build,
            latest=latest,
        )
        payload["update_blocked"] = update_blocked(
            installed_version=installed_version,
            installed_build=installed_build,
            latest=latest,
        )
        serializer = AppVersionPublicSerializer(instance=payload)
        return Response(serializer.data)


@extend_schema(tags=["App Updates"])
class AppVersionHistoryView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        blocked = _guard_update_database("AppVersionHistoryView")
        if blocked is not None:
            return blocked

        try:
            return self._get(request)
        except DatabaseError:
            logger.exception("DatabaseError in AppVersionHistoryView")
            return _database_not_ready_response(view_name="AppVersionHistoryView")

    def _get(self, request):
        platform = (request.query_params.get("platform") or AppVersion.PLATFORM_ANDROID).strip().lower()
        channel = (request.query_params.get("channel") or AppVersion.CHANNEL_STABLE).strip().lower()
        queryset = AppVersion.objects.filter(
            platform=platform,
            channel=channel,
            is_published=True,
        ).order_by("-build_number")[:20]
        serializer = AppVersionHistorySerializer(queryset, many=True)
        return Response({"results": serializer.data})


@extend_schema(tags=["App Updates"])
class AppVersionDownloadTrackView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        blocked = _guard_update_database("AppVersionDownloadTrackView")
        if blocked is not None:
            return blocked

        try:
            return self._post(request)
        except DatabaseError:
            logger.exception("DatabaseError in AppVersionDownloadTrackView")
            return _database_not_ready_response(view_name="AppVersionDownloadTrackView")

    def _post(self, request):
        version_id = request.data.get("version_id")
        if not version_id:
            return Response({"error": "version_id is required."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            version = AppVersion.objects.get(pk=version_id, is_published=True)
        except AppVersion.DoesNotExist:
            return Response({"error": "Version not found."}, status=status.HTTP_404_NOT_FOUND)
        AppVersion.objects.filter(pk=version.pk).update(download_count=version.download_count + 1)
        version.refresh_from_db(fields=["download_count"])
        return Response({"download_count": version.download_count})


@extend_schema(tags=["App Updates"])
class AppVersionPublishView(APIView):
    permission_classes = [OtaPublishTokenPermission]
    authentication_classes = []

    def post(self, request):
        blocked = _guard_update_database("AppVersionPublishView")
        if blocked is not None:
            return blocked

        try:
            return self._post(request)
        except DatabaseError:
            logger.exception("DatabaseError in AppVersionPublishView")
            return _database_not_ready_response(view_name="AppVersionPublishView")

    def _post(self, request):
        serializer = AppVersionPublishSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        version_str = data["version"]
        build_number = data["build_number"]
        platform = data["platform"]
        channel = data["channel"]

        version, _created = AppVersion.objects.get_or_create(
            platform=platform,
            channel=channel,
            version=version_str,
            build_number=build_number,
            defaults={
                "release_title": data.get("release_title") or "",
                "release_notes": data.get("release_notes") or [],
                "minimum_version": data.get("minimum_version") or "",
                "force_update": data.get("force_update", False),
                "soft_update": data.get("soft_update", True),
                "emergency_update": data.get("emergency_update", False),
            },
        )

        if data.get("release_title"):
            version.release_title = data["release_title"]
        version.release_notes = data.get("release_notes") or version.release_notes
        version.minimum_version = data.get("minimum_version") or version.minimum_version
        version.force_update = data.get("force_update", version.force_update)
        version.soft_update = data.get("soft_update", version.soft_update)
        version.emergency_update = data.get("emergency_update", version.emergency_update)

        uploaded = data.get("apk_file")
        apk_url = (data.get("apk_url") or "").strip()
        if uploaded is not None:
            checksum, size = compute_sha256(uploaded)
            saved_path, public_url = save_apk_file(
                version=version_str,
                build_number=build_number,
                uploaded_file=uploaded,
            )
            version.apk_file.name = saved_path
            version.apk_url = apk_url or public_url
            version.checksum_sha256 = checksum
            version.file_size_bytes = size
        elif apk_url:
            version.apk_url = apk_url

        version.save()
        publish_version(version, activate=data.get("activate", True))

        payload = version_payload(version, request=request)
        payload["id"] = version.id
        logger.info("Published AppVersion id=%s %s+%s", version.id, version.version, version.build_number)
        return Response(payload, status=status.HTTP_201_CREATED)
