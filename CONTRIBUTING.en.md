# Contribution workflow

[Русская версия](CONTRIBUTING.md)

## Set up a local copy

Follow the first steps in the [installation and startup guide](docs/deployment.en.md).

## Update your local checkout

Before starting work:

```bash
git switch main       # switch to the local main branch
git pull origin main  # update it from GitHub
uv sync               # synchronize pyproject.toml and uv.lock
```

## Work in a branch

Make changes in a dedicated branch and open a pull request when the work is
ready. Branch names must match the issue they close:

```text
<issue-number>-<short-description>
```

Shorten the description by using fewer words, not by abbreviating every word.
Example:

```bash
git switch -c 3-reformat-documentation
```

Before committing, inspect the changed files:

```bash
git status
```

Stage explicit files, commit the change, and push the branch:

```bash
git add <path>
git commit -m "Describe the change"
git push -u origin <issue-number>-<short-description>
```

Prefer focused commits that are easy to review. Open a pull request, link the
issue it resolves, and request review from another team member.

## Add a dependency

Use uv so both dependency declarations and the lockfile are updated:

```bash
uv add <package>
```

Commit both files:

- `pyproject.toml`
- `uv.lock`

## Issues and pull requests

Team members normally assign issues to themselves, although a lead may assign
work when coordination requires it. Every issue must have one project type:

- Bug (red)
- Feature (blue)
- Task (yellow)

Close an issue after its linked pull request has been approved and merged.
Documentation or coordination issues that do not require a pull request may be
closed after their acceptance criteria are met.

Use the branch/issue name for the pull-request title. In the description,
summarize the implementation, verification performed, limitations, and any
follow-up work. Link the issue and request at least one reviewer.

The dependency-ordered work packages and acceptance criteria are maintained in
[docs/TODO.md](docs/TODO.md).
