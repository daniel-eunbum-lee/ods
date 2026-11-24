# Project instructions for Claude Code

## Mandatory independent review (every non-trivial change, no prompt needed)

**If you were spawned as a reviewer or other subagent, skip this section: spawn no further agents
and just report your findings.**

Before reporting any non-trivial work in this repo as done, and before committing, pushing, or
merging it, have a **separate reviewer agent** go over it. This applies to code, tests, CI
workflows, configuration and behaviour-changing docs alike. Skip it for typo or formatting fixes,
or when the user says to skip it. Your own lint/test runs are necessary but are not the review.

1. Spawn a fresh, read-only reviewer with the Agent tool (general-purpose). It starts with no
   context, so the prompt must be self-contained: what the change is for, the files changed
   (`git status` / `git diff`), constraints it cannot see (see below), what to check, and the
   output format. Tell it not to edit, commit or push.
2. Ask for a prioritized list (blocker / should-fix / nit) with file:line, a concrete failure
   scenario and a suggested fix, plus what it verified versus assumed.
3. Check each finding against the files yourself, fix the real ones, and re-run lint and tests.
   If the fixes are more than trivial, have the reviewer look at them too.
4. In the final report, say what the reviewer found and what you changed. Do not merge with an
   unreviewed change.

A reviewer finding is the agent's report, not the user's approval of anything.

## Facts a reviewer or contributor needs

- The `main` ruleset requires a PR and the checks named exactly `Python 3.11 (ubuntu-latest)`,
  `Python 3.14 (ubuntu-latest)` and `Python 3.14 (windows-latest)`. Do not rename the job or matrix
  in `.github/workflows/tests.yml`.
- Package manager is `uv` (pinned in CI); keep `uv.lock` changes minimal and keep its `revision` line.
- Quality gates and the SQA approach are described in `docs/sqa.md`; update its traceability table
  when behaviour changes.
- Text files use LF (`.gitattributes`). Commit messages follow conventional commits.
