from django.test import SimpleTestCase

from update.services.github import parse_version_and_build


class GithubTagParseTests(SimpleTestCase):
    def test_ci_tag_with_build(self):
        version, build = parse_version_and_build("v1.0.0-build.40")
        self.assertEqual(version, "1.0.0")
        self.assertEqual(build, 40)

    def test_build_from_release_name(self):
        version, build = parse_version_and_build("v1.0.8", name="Duo v1.0.8 (build 108)")
        self.assertEqual(version, "1.0.8")
        self.assertEqual(build, 108)

    def test_plain_semver(self):
        version, build = parse_version_and_build("1.2.3")
        self.assertEqual(version, "1.2.3")
        self.assertEqual(build, 1)
