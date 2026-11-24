# Contributing to LLocDev repositories

These standards apply to every repository in the LLocDev organization. A repository can add its own `CONTRIBUTING.md` for what's specific to it, such as branch names and release steps (the firmware repository does). The rules on this page still apply there.

The `pr-standards / check` status enforces them on every pull request, and the repository's ruleset won't merge a PR until it passes.

## Commits

Every commit message starts with a [Conventional Commits](https://www.conventionalcommits.org) header:

```
<type>(<scope>): <description>

<optional body: what changed and why>
```

| Type | For |
|---|---|
| `feat` | New behaviour, e.g. `feat(wifi): bring up the CYW4343W radio` |
| `fix` | A bug fix, e.g. `fix(graph): stop the sample buffers overflowing on long streams` |
| `refactor`, `perf` | Code changes that keep behaviour, or make it faster |
| `test` | Tests only |
| `build`, `ci` | The build, toolchain or CI workflows |
| `docs` | Documentation only |
| `style`, `chore` | Formatting; housekeeping, including releases: `chore(release): 1.3.0` |
| `revert` | Reverting an earlier change: `revert: feat(wifi): bring up the radio` |

- **Scope** is optional: name the area the change touches (`parser`, `logging`, `wifi`, `skills`, `ci`).
- **Breaking change:** put `!` before the colon (`feat(protocol)!: drop the v1 commands`) and explain the break in the body.
- **Description:** lowercase, imperative ("add", not "added"), no full stop. The whole header is at most 100 characters.
- Exempt: merge commits (Git writes their messages), `fixup!` and `squash!` commits (the squash merge folds them away), and GitHub's own revert message, `Revert "<original header>"`.
- Bots: set the commit prefix so their PRs pass, e.g. for Dependabot `commit-message: {prefix: "chore", include: "scope"}` in `.github/dependabot.yml`.

## Pull request titles

The PR title follows the same format as a commit header. When the PR is squash-merged, the title becomes the commit subject on the target branch, so write it as one.

Keep Jira keys (`KAN-<n>`) out of PR titles and out of source code. They go in the description's Jira section and, where the repository's branch names use them, in the branch name.

## Pull request descriptions

Every repository uses the template in this repository (`pull_request_template.md`); GitHub fills it in when you open a PR.

The description has to stand on its own. Someone who has never seen the ticket, the chat thread or the bench should be able to review the PR from the description alone. Write down the background you would otherwise explain out loud.

| Section | Required | What goes in it |
|---|---|---|
| Summary | Yes | What the PR does, in one or two sentences |
| Jira | No | A link to the ticket. **Link one wherever there is one.** The check shows a notice, not a failure, when it's missing |
| Background | Yes | Why the change exists: the problem, how it was found, who is affected, how things behaved before |
| What changed | Yes | The approach, why it beat the alternatives, the key files and functions |
| How it was tested | Yes | What you ran and what you saw. For firmware: the unit, the build, the bench steps and the results |
| Screenshots / evidence | Yes | Required for user-facing changes (unit screens, PC software, printouts, command output), before and after. Otherwise "N/A" and why |
| Impact and risk | Yes | What could break and how to roll back. Firmware: measurement and certification path, stored data layout, protocol compatibility, flash/RAM |
| Reviewer notes | No | Where to start reading, what to check closely, what's out of scope |

A required section can't be left empty or hold only the template's comment. "N/A" with a reason is fine. Delete the template's comments as you fill it in: the description becomes the commit message.

## Merging

- PRs are squash-merged. The PR title becomes the commit subject and the description becomes the commit body, so the history on the target branch carries the full context. Repositories with a release flow also allow merge commits for release merges.
- A PR needs one approving review, every required check passing, and every review thread resolved.
- PRs from a `release/*` branch, and the merge of `main` back into the default branch, are merged with a merge commit and skip the commit-message check: their commits were checked in their own PRs. The title and description are still checked.
- Editing the title or description re-runs `pr-standards`, so you don't need to push again.

## When `pr-standards` fails

The check's log lists each problem.

- **Title:** edit it on the PR page.
- **Description:** fill in the sections it names.
- **Commit messages:** reword them and force-push your own branch (never a shared one):
  ```
  git rebase -i origin/<target branch>     # change "pick" to "reword" on each commit to fix
  git push --force-with-lease
  ```

## With Claude Code

The `lifeloc-dev` plugin (LLocDev/claude-skills) has two skills for this:

- `commit` writes a Conventional Commits message for the staged changes.
- `open-pr` fills in the PR template from the diff, the commits and the Jira ticket, asks you for what only you know (bench results, screenshots), runs the same check locally, and opens the PR.

## Setting up a repository

Every new repository gets the same standards:

1. Add `.github/workflows/pr-standards.yml`. In the repository, go to **Actions → New workflow** and choose **LLocDev PR standards**, or copy `workflow-templates/pr-standards.yml` from this repository. Merge it to the default branch.
2. Run `scripts/apply-standards.sh LLocDev/<repo>` from this repository, signed in to `gh` as a repository admin. It sets squash merges to use the PR title and description and adds the "PR standards" ruleset. Add `--merge-commits` and the release branch patterns for a repository with a release flow, e.g. `--merge-commits main 'release/**'`.
3. If the repository has its own branch names or release steps, write them in its own `CONTRIBUTING.md` and link back here.
