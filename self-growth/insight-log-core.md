# insight-log-core — identity-agnostic proposed methodology

> Append-only. Entries are `status: proposed` until the operator hand-ratifies (see README).
> Identity-agnostic ONLY — any entry naming a person goes in `insight-log-private.md`.

---

## 20260709-01 — Directed-visibility seam inverts the shareable/private seam

- status: proposed
- date: 2026-07-09
- context: personal-capability-agent Phase 0 scaffold (three-layer build, Session C).

A personal-layer coaching agent's dominant seam risk is NOT "private content leaking to a share
branch" (that is a dept/publish concern). It is **directed visibility**: identity must flow upward
only de-identified, score must never reach the person, and management methodology must never flow
down. The mechanical gate therefore INVERTS the donor's `check-seam.sh`: instead of scanning the
share surface for real names, it scans (a) that no identity-bearing bucket is tracked, (b) that the
upward digest is de-identified + flag-asserted, (c) that personal-facing output carries no
score/rung/tier vocabulary, (d) that no credential store was copied into a working bucket.

**Why:** the same-brain temptation is to reuse the donor gate as-is; but the risk direction is
different, so the gate's assertions must be re-derived from the threat, not copied.

**How to apply:** when forking a gate across agents, re-derive its asserts from THIS agent's threat
model; a forked gate that keeps the donor's asserts verbatim is a same-brain false-positive waiting
to happen. Verify the inverted gate with a context-blind third party + mechanical grep, never
same-brain agreement.

---

## 20260715-01 — A person-facing field's language must be pinned in the extraction contract, not the renderer

- status: proposed
- date: 2026-07-15
- context: operator noticed the insight report's 使用習慣 (bias) section rendered in English while
  the growth-direction cards rendered in zh-TW.

When an extraction sub-agent produces a field that will be surfaced to the person verbatim (the
renderer deliberately does NOT translate observation content — translating an observation would
fabricate meaning), the field's **output language must be pinned in the sub-agent's extraction
contract**, at the same place and strength as every other person-facing field. Here `growth_hint`
was pinned to zh-TW (with an example) but `bias`/`observed` had no language rule at all, so the
sub-agents defaulted to the transcript's majority language (English). The report was faithful — it
was the SOURCE that was the wrong language. Pinning it only in the renderer is impossible (it can't
translate) and pinning it "by convention" is not a gate — an unspecified field's language is
non-deterministic across runs and WILL drift back.

**Why:** the failure presents as a rendering/localization bug ("why is this section English?") but
the root cause is a contract gap one layer upstream. Chasing it in the renderer would have added a
translation step that violates the no-translate-observations rule; the only recur-proof fix is in
the contract. A rule that lives only in prose expectation, not in the structural contract the
sub-agent reads, is silently skipped (this repo's standing discipline).

**How to apply:** audit every extraction field for "does this reach the person, and if so is its
language/register pinned in the sub-agent contract?" Any person-facing field inherits the same
language pin as the canonical one (`growth_hint`); internal-only fields (`evidence_refs`,
`signal_tier`) may stay any language. When a person-facing rendering looks wrong, check whether the
renderer is faithfully passing through wrong SOURCE before touching the renderer.

---

## 20260715-02 — A denylist regex must match the general shape, not a hardcoded example token; and same-brain verification cannot catch its own incomplete fix

- status: proposed
- date: 2026-07-15
- context: hardening the RL4 identity/self-containment gates to catch Windows paths
  (`C:\Users\<name>`). The first fix pinned the drive letter case-flexibly (`[A-Za-z]:`) but wrote
  the folder segment as the literal `Users`. A context-blind verifier then showed a lowercase
  `c:\users\alice\secret.txt` sailing past RL4 gate (b) — an upward-file identity leak — with the
  gate still exiting 0.

A security/identity denylist regex must match the **general structural shape** of the thing it
forbids, not one capitalized example of it. `[A-Za-z]:\Users\…` looks case-safe because the drive
letter is a class, but the hardcoded `Users` silently narrows the match to one folder in one case —
so `c:\users\…`, `C:\Documents\…`, `d:\temp\…` all slip through. The correct form matches any
drive-rooted path (`[A-Za-z]:\+[^\...]+\+…`). This is the denylist dual of the standing "a rule in
prose is silently skipped; it needs a structural gate" discipline: a gate whose pattern is too
specific is a *silent* hole — it passes, so nothing looks wrong.

Second, load-bearing lesson: **the person who wrote a fix is the worst person to verify it.** This
hole was introduced while fixing the very same Windows-path problem, and a same-brain check would
have re-confirmed the capitalized case it was written against and declared victory. Only a
context-blind verifier — told just the *claim*, asked to *refute* it, running a real probe with a
lowercase path — surfaced it. This mirrors the de-id audit's earlier same-brain false-NEGATIVE
(`worktemp/DEID-AUDIT-2026-07-09.md`): same-brain verification systematically misses the gap the
author's own mental model created.

**Why:** an over-specific denylist pattern fails OPEN (it passes the thing it should catch) with no
error to notice — the most dangerous failure mode for a security gate. And an author verifying their
own fix tests the case they were already thinking about, not the case they forgot.

**How to apply:** (1) When writing a deny/leak regex, match the general shape (drive-rooted path,
any-user home, any email) and add a regression fixture for the *variant you did NOT think of first*
(lowercase, alternate folder, alternate separator) to lock the hole shut. (2) For any change to an
RL4/gate/security surface — especially one you just authored — send it through a context-blind
adversarial verifier (Workflow, default-refute, isolated worktree, given only the claim, never the
diff or the expected answer) before trusting it. Same-brain green is not green. See
[[20260709-01]] (the seam gate whose asserts must be re-derived, not copied).
