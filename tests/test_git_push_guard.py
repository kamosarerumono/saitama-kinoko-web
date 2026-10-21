import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


GIT = os.environ.get("GIT_EXECUTABLE") or shutil.which("git") or "git"
HOOK = Path(__file__).resolve().parents[1] / ".githooks" / "pre-push"


class GitPushGuardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.remote = self.root / "origin.git"
        self.repo = self.root / "repo"
        self.repo_hook = self.repo / ".githooks" / "pre-push"
        self.run_git("init", "--bare", "--initial-branch=master", str(self.remote), cwd=self.root)
        self.repo.mkdir()
        self.run_git("init", "--initial-branch=master", cwd=self.repo)
        self.run_git("config", "user.name", "Push Guard Test", cwd=self.repo)
        self.run_git("config", "user.email", "push-guard@example.invalid", cwd=self.repo)
        self.repo_hook.parent.mkdir()
        shutil.copyfile(HOOK, self.repo_hook)
        self.run_git("config", "core.hooksPath", ".githooks", cwd=self.repo)
        self.run_git("remote", "add", "origin", str(self.remote), cwd=self.repo)
        self.run_git("config", "codex.pushGuard.expectedRemote", str(self.remote), cwd=self.repo)
        (self.repo / "tracked.txt").write_text("base\n", encoding="utf-8")
        self.commit("base")
        self.run_git("push", "-u", "origin", "refs/heads/master:refs/heads/master", cwd=self.repo)
        self.run_git("switch", "-c", "feature/publish-guard", cwd=self.repo)
        (self.repo / "tracked.txt").write_text("feature\n", encoding="utf-8")
        self.commit("feature")

    def tearDown(self):
        self.temp.cleanup()

    def run_git(self, *args, cwd, check=True):
        result = subprocess.run(
            [GIT, *args], cwd=cwd, text=True, capture_output=True, check=False
        )
        if check and result.returncode:
            self.fail(f"git {' '.join(args)} failed: {result.stderr}")
        return result

    def commit(self, message):
        self.run_git("add", "tracked.txt", cwd=self.repo)
        self.run_git("commit", "-m", message, cwd=self.repo)

    def remote_sha(self, ref):
        result = self.run_git("ls-remote", "origin", ref, cwd=self.repo)
        return result.stdout.split()[0] if result.stdout.strip() else None

    def test_feature_upstreaming_to_master_is_blocked_before_remote_changes(self):
        self.run_git("branch", "--set-upstream-to=origin/master", cwd=self.repo)
        self.run_git("config", "push.default", "upstream", cwd=self.repo)
        master_before = self.remote_sha("refs/heads/master")
        result = self.run_git("push", cwd=self.repo, check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("feature branch cannot be pushed to master or main", result.stderr)
        self.assertEqual(self.remote_sha("refs/heads/master"), master_before)

    def test_upstream_origin_master_cannot_be_used_for_feature_destination(self):
        self.run_git("branch", "--set-upstream-to=origin/master", cwd=self.repo)
        result = self.run_git(
            "push", "origin",
            "refs/heads/feature/publish-guard:refs/heads/feature/publish-guard",
            cwd=self.repo, check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("branch upstream ref differs", result.stderr)
        self.assertIsNone(self.remote_sha("refs/heads/feature/publish-guard"))

    def test_exact_feature_remote_ref_and_sha_pushes(self):
        self.run_git("config", "branch.feature/publish-guard.remote", "origin", cwd=self.repo)
        self.run_git(
            "config", "branch.feature/publish-guard.merge",
            "refs/heads/feature/publish-guard", cwd=self.repo,
        )
        expected = self.run_git("rev-parse", "refs/heads/feature/publish-guard", cwd=self.repo).stdout.strip()
        result = self.run_git(
            "push", "origin",
            "refs/heads/feature/publish-guard:refs/heads/feature/publish-guard",
            cwd=self.repo,
        )
        self.assertIn(expected, result.stderr + result.stdout)
        self.assertEqual(self.remote_sha("refs/heads/feature/publish-guard"), expected)

    def test_same_name_master_maintenance_push_remains_allowed(self):
        self.run_git("switch", "master", cwd=self.repo)
        (self.repo / "tracked.txt").write_text("approved maintenance\n", encoding="utf-8")
        self.commit("maintenance")
        expected = self.run_git("rev-parse", "refs/heads/master", cwd=self.repo).stdout.strip()
        self.run_git(
            "push", "origin", "refs/heads/master:refs/heads/master", cwd=self.repo
        )
        self.assertEqual(self.remote_sha("refs/heads/master"), expected)

    def test_changed_origin_identity_is_blocked(self):
        self.run_git("config", "codex.pushGuard.expectedRemote", "different-origin", cwd=self.repo)
        result = self.run_git(
            "push", "origin",
            "refs/heads/feature/publish-guard:refs/heads/feature/publish-guard",
            cwd=self.repo, check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("push remote does not match", result.stderr)
        self.assertIsNone(self.remote_sha("refs/heads/feature/publish-guard"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
