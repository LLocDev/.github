"""Check a pull request against the LLocDev contribution standards (CONTRIBUTING.md).

    python3 scripts/check_pr.py --title "<PR title>" --body-file <file>
                                [--commits-file <file> | --git-range <base>..HEAD] [--bot]
    python3 scripts/check_pr.py --header "<commit header>"

    --title         the PR title
    --body-file     a file holding the PR description (empty file = no description)
    --commits-file  a JSON list of commits, as returned by the GitHub API
                    (GET /repos/<owner>/<repo>/pulls/<n>/commits): each item needs
                    "sha", "commit.message" and "parents"
    --git-range     read the commits from the local repository instead, e.g. origin/develop..HEAD
    --title-file    read the PR title from a file instead (safer for titles with backticks or quotes)
    --head          the PR's head branch. Commits are not checked when it is release/*, or main
                    (the merge back to develop after a release): those commits were checked in
                    their own PRs, or predate the standards.
    --bot           the PR was opened by a bot: skip the description check
    --header        check one commit header (the first line of a commit message) and nothing else

Prints each problem and exits 1 if there are any. Prints a GitHub Actions notice (not a
failure) when the description has no Jira link.

The rules:
  - The PR title and the first line of every commit follow Conventional Commits
    (https://www.conventionalcommits.org): <type>(<optional scope>)<optional !>: <description>.
    Merge commits are skipped, and so are fixup!/squash! commits, which the squash merge
    folds away. GitHub's own revert title, Revert "<original header>", is accepted.
  - The PR title has no Jira key: it becomes the commit subject when the PR is squash-merged.
  - The description has each required section from the PR template, filled in. "N/A" with
    a reason counts as filled in; an HTML comment on its own does not.
"""
import argparse
import json
import re
import subprocess
import sys

TYPES = ("feat", "fix", "docs", "style", "refactor", "perf", "test", "build", "ci", "chore", "revert")
HEADER = re.compile(r"^(?:%s)(?:\([A-Za-z0-9._/-]+\))?!?: \S" % "|".join(TYPES))
GITHUB_REVERT = re.compile(r'^Revert ".+"$')
AUTOSQUASH = re.compile(r"^(?:fixup|squash|amend)! ")
# Head branches whose commits are not checked: their commits were checked in their own PRs.
UNCHECKED_HEADS = re.compile(r"^(?:release/.+|main)$")
MAX_HEADER = 100
# Jira projects whose keys must stay out of PR titles. A generic KEY-123 pattern would also
# catch names like UTF-8 or SHA-256, so list the projects.
JIRA_PROJECTS = ("KAN",)
JIRA_KEY = re.compile(r"\b(?:%s)-\d+\b" % "|".join(JIRA_PROJECTS))
JIRA_LINK = re.compile(r"https://[a-z0-9-]+\.atlassian\.net/browse/[A-Z][A-Z0-9]+-\d+")

REQUIRED_SECTIONS = (
    "Summary",
    "Background",
    "What changed",
    "How it was tested",
    "Screenshots / evidence",
    "Impact and risk",
)
EXAMPLE = "fix(parser): handle /power arguments"


def header_problems(header, what):
    """Problems with one Conventional Commits header (a PR title or a commit subject)."""
    header = (header or "").strip()
    if GITHUB_REVERT.match(header):
        return []
    if not HEADER.match(header):
        return [
            "%s '%s' doesn't follow Conventional Commits: use <type>(<scope>): <description>, "
            "e.g. '%s'. Types: %s." % (what, header, EXAMPLE, ", ".join(TYPES))
        ]
    if len(header) > MAX_HEADER:
        return ["%s is %d characters; keep it to %d or fewer." % (what, len(header), MAX_HEADER)]
    return []


def title_problems(title):
    problems = header_problems(title, "PR title")
    if not problems and JIRA_KEY.search(title):
        problems.append(
            "Take the Jira key out of the PR title: it becomes the commit subject. "
            "Link the ticket in the description's Jira section instead."
        )
    return problems


def commit_problems(commits):
    problems = []
    for c in commits:
        if len(c.get("parents") or []) > 1:
            continue  # merge commit: its message is generated
        message = (c.get("commit") or {}).get("message") or ""
        subject = message.splitlines()[0] if message else ""
        if AUTOSQUASH.match(subject):
            continue  # folded into the squash commit
        for p in header_problems(subject, "Commit %s" % (c.get("sha") or "")[:7]):
            problems.append(p)
    return problems


def _strip_comments(text):
    return re.sub(r"<!--.*?-->", "", text, flags=re.S)


def sections(body):
    """Map each '## ' heading in the body (lowercased) to the text under it."""
    found = {}
    current = None
    fence = None
    for line in _strip_comments(body or "").splitlines():
        f = re.match(r"^\s*(```|~~~)", line)
        if f:
            if fence is None:
                fence = f.group(1)
            elif f.group(1) == fence:
                fence = None
        m = None if fence or f else re.match(r"^##\s+(.+?)\s*#*\s*$", line)
        if m:
            current = m.group(1).strip().lower()
            found[current] = []
        elif current is not None:
            found[current].append(line)
    return {k: "\n".join(v).strip() for k, v in found.items()}


def body_problems(body):
    if not (body or "").strip():
        return [
            "The PR has no description. Fill in the PR template: sections %s."
            % ", ".join("'%s'" % s for s in REQUIRED_SECTIONS)
        ]
    found = sections(body)
    problems = []
    for name in REQUIRED_SECTIONS:
        key = name.lower()
        if key not in found:
            problems.append("The description is missing the '## %s' section." % name)
        elif not found[key]:
            problems.append(
                "The '## %s' section is empty. Fill it in, or write 'N/A' and why." % name
            )
    return problems


def has_jira_link(body):
    return bool(JIRA_LINK.search(_strip_comments(body or "")))


def check(title, body, commits, bot=False, head=None):
    """Return (problems, notices) for this pull request."""
    problems = title_problems(title)
    if not (head and UNCHECKED_HEADS.match(head)):
        problems += commit_problems(commits)
    notices = []
    if not bot:
        problems += body_problems(body)
        if not has_jira_link(body):
            notices.append(
                "No Jira ticket linked. If this work has a ticket, add its link in the '## Jira' section."
            )
    return problems, notices


def git_commits(rev_range):
    """The commits in a local revision range, in the GitHub API's shape."""
    out = subprocess.run(
        ["git", "log", "--format=%H%x00%P%x00%B%x1e", rev_range],
        capture_output=True, text=True, check=True, encoding="utf-8",
    ).stdout
    commits = []
    for record in out.split("\x1e"):
        record = record.strip("\n")
        if not record:
            continue
        sha, parents, message = record.split("\x00", 2)
        commits.append({"sha": sha, "commit": {"message": message}, "parents": parents.split()})
    return commits


def report(problems, notices):
    for n in notices:
        print("::notice::%s" % n)
    for p in problems:
        print("::error::%s" % p)
    if problems:
        print("\n%d problem(s). The standards are in CONTRIBUTING.md in LLocDev/.github." % len(problems))
        return 1
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--header")
    ap.add_argument("--title")
    ap.add_argument("--title-file")
    ap.add_argument("--head")
    ap.add_argument("--body-file")
    commits_from = ap.add_mutually_exclusive_group()
    commits_from.add_argument("--commits-file")
    commits_from.add_argument("--git-range")
    ap.add_argument("--bot", action="store_true")
    args = ap.parse_args(argv)
    # Windows consoles default to a legacy code page; titles can hold any character.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    if args.title_file:
        with open(args.title_file, encoding="utf-8") as f:
            args.title = f.read().strip()
    if args.header is not None:
        if report(header_problems(args.header, "Commit header"), []):
            return 1
        print("Commit header follows Conventional Commits.")
        return 0
    if args.title is None or args.body_file is None:
        ap.error("--title (or --title-file) and --body-file are required (or use --header)")

    with open(args.body_file, encoding="utf-8") as f:
        body = f.read()
    commits = []
    if args.commits_file:
        with open(args.commits_file, encoding="utf-8") as f:
            commits = json.load(f)
    elif args.git_range:
        commits = git_commits(args.git_range)

    problems, notices = check(args.title, body, commits, args.bot, args.head)
    if not (args.commits_file or args.git_range):
        notices.append("Commits not checked: pass --git-range <target>..HEAD (or --commits-file) to check them.")
    if report(problems, notices):
        return 1
    print("PR title, commits and description follow the LLocDev standards.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
