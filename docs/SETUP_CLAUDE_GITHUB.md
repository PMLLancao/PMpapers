# Turning on @claude in this repository (one-time, repository owner)

The workflow file `.github/workflows/claude.yml` is already in place. Two steps need the owner's account:

1. **Install the Claude GitHub App** at https://github.com/apps/claude → Install → choose *Only select repositories* → **PMpapers**.
2. **Add a secret** in this repository: Settings → Secrets and variables → Actions → New repository secret.
   - Name `ANTHROPIC_API_KEY`, value = an API key from https://platform.claude.com (pay per use), **or**
   - Name `CLAUDE_CODE_OAUTH_TOKEN`, value from running `claude setup-token` in Claude Code (uses a Claude Pro/Max subscription); then swap the two marked lines in `claude.yml`.

Test: comment `@claude please run the regression tests and report the result` on Issue #1.

Notes: only people with write access can trigger Claude. Claude's own comments cannot trigger another run (loop protection).
Each run uses GitHub Actions minutes plus Claude usage; runs are capped at 30 minutes and 40 turns.
