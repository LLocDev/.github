import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import check_pr  # noqa: E402

TEMPLATE = os.path.join(HERE, "..", "pull_request_template.md")

GOOD_BODY = """## Summary
Stops the graph buffers overflowing.

## Jira
https://2520-llc.atlassian.net/browse/KAN-65

## Background
Streams longer than 250 samples wrote past the array.

## What changed
Each callback passes a local variable.

## How it was tested
Unit test under AddressSanitizer; passive test on the dev unit.

## Screenshots / evidence
N/A: no screen change.

## Impact and risk
Low: the queues already copied the item.
"""


def commit(sha, message, parents=1):
    return {"sha": sha, "commit": {"message": message}, "parents": [{}] * parents}


class TitleTests(unittest.TestCase):
    def test_good_titles(self):
        for t in ("fix(parser): handle /power arguments", "feat!: drop v1 protocol",
                  "ci: add pr-standards", "chore(release): 1.3.0", "revert: feat(wifi): bring up the radio",
                  "refactor(parser)!: split the transport layer", "ci(.github/workflows): update checks"):
            self.assertEqual(check_pr.title_problems(t), [], t)

    def test_bad_titles(self):
        for t in ("Fix the parser", "fix:missing space", "feature(x): y", "", "skill: add pr-review-loop",
                  "fix: ", "Fix: capitalised type", "fix(): empty scope", "fix(parser) missing colon"):
            self.assertTrue(check_pr.title_problems(t), t)

    def test_jira_key_in_title(self):
        for t in ("fix(graph): KAN-65 overflow", "fix(KAN-65): stop the overflow"):
            self.assertIn("Jira key", check_pr.title_problems(t)[0], t)

    def test_names_like_utf8_are_not_jira_keys(self):
        self.assertEqual(check_pr.title_problems("fix(log): write UTF-8 and SHA-256 names"), [])

    def test_too_long(self):
        self.assertIn("characters", check_pr.title_problems("fix: " + "x" * 120)[0])


class CommitTests(unittest.TestCase):
    def test_good_and_merge_commits_pass(self):
        commits = [commit("a" * 40, "fix(graph): use a local\n\nbody"),
                   commit("b" * 40, "Merge branch 'develop' into feature/x", parents=2)]
        self.assertEqual(check_pr.commit_problems(commits), [])

    def test_bad_commit_named_by_short_sha(self):
        problems = check_pr.commit_problems([commit("abcdef1234", "wip")])
        self.assertEqual(len(problems), 1)
        self.assertIn("Commit abcdef1", problems[0])

    def test_jira_key_allowed_in_commits(self):
        # Branch commits don't reach develop (squash merge), so only the title is checked for keys.
        self.assertEqual(check_pr.commit_problems([commit("c" * 40, "fix: KAN-65 follow-up")]), [])


class ExemptionTests(unittest.TestCase):
    def test_github_revert_title(self):
        self.assertEqual(check_pr.title_problems('Revert "feat(wifi): bring up the radio"'), [])

    def test_fixup_commits_skipped(self):
        self.assertEqual(check_pr.commit_problems([commit("d" * 40, "fixup! fix: x"),
                                                   commit("e" * 40, "squash! fix: x")]), [])

    def test_release_and_back_merge_heads_skip_commits(self):
        bad = [commit("f" * 40, "Add a contributor guide")]
        for head in ("release/1.3", "main"):
            problems, warnings, _ = check_pr.check("chore(release): 1.3.0", GOOD_BODY, bad, head=head)
            self.assertEqual((problems, warnings), ([], []), head)

    def test_hotfix_commits_block(self):
        # hotfix/* merges into main with a merge commit, so its commit messages reach history.
        bad = [commit("f" * 40, "Add a contributor guide")]
        problems, warnings, _ = check_pr.check("fix: x", GOOD_BODY, bad, head="hotfix/1.3.1")
        self.assertEqual((len(problems), warnings), (1, []))

    def test_squashed_branch_commits_only_warn(self):
        bad = [commit("f" * 40, "Update stm32f4xx_it.c")]
        for head in ("feature/KAN-1-x", "tools/x", "skill/x", None):
            problems, warnings, _ = check_pr.check("fix: x", GOOD_BODY, bad, head=head)
            self.assertEqual((problems, len(warnings)), ([], 1), head)


class BodyTests(unittest.TestCase):
    def test_heading_inside_code_fence_is_not_a_section(self):
        body = GOOD_BODY.replace("Unit test under AddressSanitizer; passive test on the dev unit.",
                                 "Ran:\n```\n## Summary\n```\nPassed.")
        self.assertEqual(check_pr.body_problems(body), [])
        self.assertIn("Ran:", check_pr.sections(body)["how it was tested"])

    def test_crlf_body(self):
        self.assertEqual(check_pr.body_problems(GOOD_BODY.replace("\n", "\r\n")), [])

    def test_good_body(self):
        self.assertEqual(check_pr.body_problems(GOOD_BODY), [])

    def test_empty_body(self):
        self.assertIn("no description", check_pr.body_problems("  \n")[0])

    def test_untouched_template_fails_every_required_section(self):
        with open(TEMPLATE, encoding="utf-8") as f:
            problems = check_pr.body_problems(f.read())
        self.assertEqual(len(problems), len(check_pr.REQUIRED_SECTIONS))
        self.assertTrue(all("empty" in p for p in problems))

    def test_missing_section(self):
        body = GOOD_BODY.replace("## Impact and risk\nLow: the queues already copied the item.\n", "")
        self.assertEqual(check_pr.body_problems(body),
                         ["The description is missing the '## Impact and risk' section."])

    def test_headings_case_insensitive(self):
        self.assertEqual(check_pr.body_problems(GOOD_BODY.replace("## What changed", "## What Changed")), [])

    def test_template_has_every_required_section(self):
        with open(TEMPLATE, encoding="utf-8") as f:
            found = check_pr.sections(f.read())
        for name in check_pr.REQUIRED_SECTIONS:
            self.assertIn(name.lower(), found)

    def test_jira_optional_but_noticed(self):
        body = GOOD_BODY.replace("https://2520-llc.atlassian.net/browse/KAN-65", "")
        problems, _, notices = check_pr.check("fix: x", body, [])
        self.assertEqual(problems, [])
        self.assertEqual(len(notices), 1)

    def test_jira_link_in_comment_does_not_count(self):
        self.assertFalse(check_pr.has_jira_link("<!-- https://2520-llc.atlassian.net/browse/KAN-1 -->"))

    def test_bot_skips_description(self):
        problems, warnings, notices = check_pr.check("chore(deps): bump x", "", [], bot=True)
        self.assertEqual((problems, warnings, notices), ([], [], []))


class CliTests(unittest.TestCase):
    def run_cli(self, title, body, commits):
        with tempfile.TemporaryDirectory() as d:
            bf, cf = os.path.join(d, "body"), os.path.join(d, "commits")
            with open(bf, "w", encoding="utf-8") as f:
                f.write(body)
            with open(cf, "w", encoding="utf-8") as f:
                json.dump(commits, f)
            return subprocess.run([sys.executable, os.path.join(HERE, "check_pr.py"), "--title", title,
                                   "--body-file", bf, "--commits-file", cf], capture_output=True, text=True)

    def test_pass(self):
        r = self.run_cli("fix(graph): stop the overflow", GOOD_BODY, [commit("a" * 40, "fix: x")])
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_fail_prints_errors(self):
        r = self.run_cli("Graph fix", "", [commit("a" * 40, "wip")])
        self.assertEqual(r.returncode, 1)
        self.assertEqual(r.stdout.count("::error::"), 2)  # title and description
        self.assertEqual(r.stdout.count("::warning::"), 1)  # the commit: no --head, so not a hotfix

    def test_header_mode(self):
        script = os.path.join(HERE, "check_pr.py")
        ok = subprocess.run([sys.executable, script, "--header", "docs: fix a typo"], capture_output=True, text=True)
        bad = subprocess.run([sys.executable, script, "--header", "typo"], capture_output=True, text=True)
        self.assertEqual((ok.returncode, bad.returncode), (0, 1))

    def test_title_file(self):
        with tempfile.TemporaryDirectory() as d:
            tf, bf = os.path.join(d, "title"), os.path.join(d, "body")
            with open(tf, "w", encoding="utf-8") as f:
                f.write("fix(parser): handle `/power` arguments → done\n")
            with open(bf, "w", encoding="utf-8") as f:
                f.write(GOOD_BODY)
            r = subprocess.run([sys.executable, os.path.join(HERE, "check_pr.py"), "--title-file", tf,
                                "--body-file", bf], capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_notice_when_commits_not_given(self):
        with tempfile.TemporaryDirectory() as d:
            bf = os.path.join(d, "body")
            with open(bf, "w", encoding="utf-8") as f:
                f.write(GOOD_BODY)
            r = subprocess.run([sys.executable, os.path.join(HERE, "check_pr.py"), "--title", "fix: x",
                                "--body-file", bf], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0)
        self.assertIn("Commits not checked", r.stdout)

    def test_title_required_without_header(self):
        r = subprocess.run([sys.executable, os.path.join(HERE, "check_pr.py")], capture_output=True, text=True)
        self.assertEqual(r.returncode, 2)


class GitRangeTests(unittest.TestCase):
    def test_reads_messages_and_merge_parents(self):
        with tempfile.TemporaryDirectory() as d:
            def git(*a):
                subprocess.run(["git", "-C", d, "-c", "user.name=t", "-c", "user.email=t@t", *a],
                               check=True, capture_output=True)
            git("init", "-q", "-b", "main")
            git("commit", "-q", "--allow-empty", "-m", "chore: start")
            git("switch", "-q", "-c", "side")
            git("commit", "-q", "--allow-empty", "-m", "wip\n\nbody line")
            git("switch", "-q", "main")
            git("commit", "-q", "--allow-empty", "-m", "fix: on main")
            git("merge", "-q", "--no-ff", "-m", "Merge branch 'side'", "side")
            cwd = os.getcwd()
            os.chdir(d)
            try:
                commits = check_pr.git_commits("HEAD~2..HEAD")
            finally:
                os.chdir(cwd)
        messages = sorted(c["commit"]["message"].splitlines()[0] for c in commits)
        self.assertEqual(messages, ["Merge branch 'side'", "fix: on main", "wip"])
        problems = check_pr.commit_problems(commits)
        self.assertEqual(len(problems), 1)
        self.assertIn("'wip'", problems[0])


if __name__ == "__main__":
    unittest.main()
