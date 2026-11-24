# LLocDev/.github

Organization-wide defaults for LLocDev repositories.

| Path | What it is |
|---|---|
| `CONTRIBUTING.md` | The contribution standards: commit messages, PR titles, PR descriptions, merging. GitHub shows it in any repository that has no `CONTRIBUTING.md` of its own. |
| `pull_request_template.md` | The PR description template. GitHub uses it in every repository that has no template of its own. |
| `.github/workflows/standards.yml` | The reusable `pr-standards` check every repository calls. |
| `scripts/check_pr.py` | The checker the workflow runs, with its tests in `scripts/test_check_pr.py`. |
| `scripts/apply-standards.sh` | Sets a repository's merge settings and its "PR standards" ruleset. |
| `workflow-templates/pr-standards.yml` | The caller workflow, offered under **Actions → New workflow** in every LLocDev repository. |

Every repository calls the check from `main` here, so a change merged to `main` applies to every repository at once. Review changes to the checker with that in mind; its tests run inside the required check on this repository's PRs.

This repository is public so GitHub can apply the template and the contributing guide to the private repositories. Keep anything confidential out of it.

Run the checker on a draft locally:

```
python3 scripts/check_pr.py --title "fix(parser): handle /power arguments" --body-file body.md
python3 -m unittest discover -s scripts -p 'test_*.py'
```
