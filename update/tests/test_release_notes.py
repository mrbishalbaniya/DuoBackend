from django.test import SimpleTestCase

from update.services.release_notes import parse_release_notes, resolve_release_title, sanitize_release_notes


class ReleaseNotesSanitizeTests(SimpleTestCase):
    def test_filters_github_release_body(self):
        body = """
        Automated release from `main` @ 0bee571321cf14d1ee3bc3ee70516e8516511d7a.
        - APK: `app-release.apk` (install on Android)
        - AAB: `app-release.aab` (Play Store upload)
        - Signing SHA-256: certificate SHA-256 digest
        ### Install help
        If you see **"package conflicts with an existing package"**:
        Improved matching recommendations
        Faster chat performance
        """
        notes = sanitize_release_notes(body)
        self.assertEqual(
            notes,
            [
                "Improved matching recommendations.",
                "Faster chat performance.",
            ],
        )
        joined = " ".join(notes).lower()
        self.assertNotIn("apk", joined)
        self.assertNotIn("sha", joined)
        self.assertNotIn("0bee571", joined)

    def test_fallback_when_only_technical_content(self):
        notes = sanitize_release_notes(
            "Automated release from main @ abcdef1234567\n- APK: app-release.apk"
        )
        self.assertEqual(
            notes,
            [
                "General performance improvements.",
                "Bug fixes.",
                "Improved stability.",
            ],
        )

    def test_parse_keeps_empty_without_fallback(self):
        self.assertEqual(parse_release_notes(""), [])
        self.assertEqual(parse_release_notes(["APK: file.apk"]), [])

    def test_resolve_title(self):
        self.assertEqual(
            resolve_release_title("Performance & Stability Update"),
            "Performance & Stability Update",
        )
        self.assertEqual(
            resolve_release_title("", version="1.0.0"),
            "Performance & Stability Update",
        )
