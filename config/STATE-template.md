# STATE-template — operational status (SHAREABLE, identity-agnostic)

> This is the shareable template. The live operational state with a real machine path / real
> coverage lives in the PRIVATE `config/STATE.md` (gitignored). Copy this shape; never put a real
> person / machine path / identity here.

## Current status

- Phase: <P0 | P1 | ...>
- Self-containment gate: `validate-selfcontainment.sh` → <exit 0 | fail>
- Visibility seam gate: `check-visibility-seam.sh` → <exit 0 | fail>

## Next Action

- <single concrete next step the next fresh agent should take>

## Coverage (source_scope honesty — RL4 (iv))

| source | storage | ingested? | note |
|--------|---------|-----------|------|
| Claude Code CLI | local jsonl | <yes|no> | baseline |
| Codex CLI | local jsonl | <deferred> | highest-risk de-id source |
| ChatGPT / Claude Desktop | server-only | <blind spot> | export-archive only |
