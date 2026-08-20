# Security model

## What this document is for

Caiman handles vendor and customer documentation under NDA. This file states
what the system defends against, what it does not, and where enforcement
actually lives. Being precise about the limits is more useful than claiming
broad protection — a control that feels enforced but isn't is worse than no
control.

The short version: **the human picks the agent, and Caiman makes that choice
consequential.** There is no software boundary here, by design. What there is
instead is a decision made at the moment the human actually knows what the work
is, and a materialization step that makes a wrong choice surface as a missing
file rather than as a silent disclosure.

---

## The asymmetry that shapes everything

Two kinds of document arrive under something called an NDA, and treating them
the same forces the expensive treatment onto the cheap case.

**Chip vendor documentation** — reference manuals, datasheets, errata from NXP,
TI, and the rest — is nominally confidential and practically semi-public.
Click-through agreements, wide mirroring, hundreds of suppliers holding
identical copies, and every frontier model has almost certainly seen the family
already. Gating it is expensive and buys close to nothing.

**Customer specifications** — an OEM's requirements for secure boot, secure
onboard communication, flashing, diagnostics, and the program deviations that
amend them — are genuinely closely held. A handful of suppliers have them, the
contents identify whose they are, and the agreement is with the party whose
business you are trying to keep. A leak here is a commercial event.

So: **vendor documentation is treated as public. Customer material is
compartmented.** This is a deliberate prioritization, not an oversight. If a
genuinely restricted vendor document ever arrives, the compartment mechanism
handles it with no new machinery — nothing is foreclosed by deprioritizing it
now.

---

## Classification: public, or compartmented

There is no tier scale. There are two things a document can be.

**Public.** Asserted at ingest. Materialized for any session, readable by any
model.

**Compartmented.** Carries one or more compartment labels naming *whose secret
it is*.

A compartment is borrowed from how classified material is actually handled,
where clearance and compartment are separate ideas. Clearance is a scale —
higher sees more, and the ordering is total. A compartment is a category: being
read into one tells you nothing about another, and two things can be equally
sensitive and mutually invisible.

That distinction is the one Caiman needs. OEM Alpha's specification and OEM
Beta's specification are both confidential, both at the same sensitivity, and
must be mutually unreachable. A sensitivity number cannot express that, because
whatever numbers you assign, one is greater than or equal to the other and sees
it.

| Document | Label |
|---|---|
| NXP S32K3 reference manual | `public` |
| OEM Alpha base spec set 3.2 | `compartment:oem-alpha` |
| Falcon program deviations | `compartment:oem-alpha`, `compartment:falcon` |
| OEM Beta spec set 2.0 | `compartment:oem-beta` |

A project declares its compartments; a session inherits them from its project.
A document is visible when its compartments are a **subset** of the session's.
A Falcon session holds `oem-alpha` and `falcon`, so it sees the first three rows
and never the fourth — not because the fourth is more secret, but because it
belongs to someone else.

**Default to per-counterparty**, because that is how the NDA is written and it
lets a base spec be shared naturally across that customer's programs. Add a
program compartment only to documents that need the tighter scope, as in row
three. Nothing has to be migrated if you start simple and tighten later.

**Missing metadata is neither public nor compartmented, and stays unreachable.**
That is invariant I-1, and it is unchanged by any of this. Both labels are
assigned at ingest from provenance, never inferred from content, and never
widened by a downstream stage.

---

## The primary control: the human picks the agent

Every mechanism this project considered and rejected — a server that refuses, a
kernel that returns `EACCES`, a filter that excludes — acts at the moment of
*read*. At read time nobody knows what the work is for.

At **session start**, the human knows exactly: "I'm adding a diagnostic routine
for Falcon" or "I'm fixing a CAN driver bug." That is the moment the decision is
cheap, informed, and unambiguous, and it is a moment the harness already
interrupts them at to ask which project they are on. Asking one more question
costs nothing.

So the philosophy is explicit: **the engineer is responsible for picking the
right agent for the task.** Generic work starts a session with a frontier
harness. Work that touches customer material starts a session with a local
model. Caiman does not adjudicate that choice; it makes it consequential.

## The fail-safe: differential materialization

Human routing on its own would be a policy in a document. What makes it a
control is that Caiman materializes different corpora for different agents, so
the choice has physical effect.

Consider both ways the human can get it wrong:

- **Picked a frontier agent, work turns out to need OEM specs.** The specs are
  not in the worktree. The agent cannot find them, and the brief has told it to
  stop and say so rather than improvise. The engineer restarts the session
  sealed. Loud, harmless, self-correcting.
- **Picked a local agent, work turns out to be generic.** A weaker model did
  work it did not need to. That is the whole cost.

Both error directions fail safe. That is the property the design is buying, and
it comes from keeping differential materialization even after dropping
enforcement.

### Caiman owns the agent map

```toml
# ~/.config/caiman/agents.toml
# Which agents may receive compartmented material.

[agent.claude-code]
receives = "public"      # sends prompts to a third party

[agent.cursor]
receives = "public"

[agent.codex-local]
receives = "all"         # self-hosted model, no egress
```

The harness passes the agent's **name**, not a policy decision:

```
caiman sync --project falcon --version B-sample \
            --agent claude-code --into .caiman/
```

Caiman resolves the project version, looks up the agent, filters the document
set, materializes it, and writes a brief stating the session mode.

Caiman holds this map rather than the harness for four reasons:

1. **One place to answer the question.** "What could a Claude Code session on
   Falcon see?" is a config file and a `--dry-run`, not an audit across however
   many harnesses get tried.
2. **An unknown agent fails closed.** A name Caiman has never heard of is
   refused, not guessed at. Adding a backend is a deliberate one-line edit to a
   file that shows up in a diff — exactly the friction that decision deserves.
   If the harness owned the policy, an unconfigured agent would receive whatever
   the harness happened to say.
3. **Policy survives harness changes.** Two or three harnesses will get tried.
   The map should not be re-entered each time, or drift between them.
4. **The brief can state the session mode truthfully**, because the same code
   computed it.

The harness keeps what it is better at: knowing which backends exist, asking the
human, and running the session.

### The agent is told, not merely constrained

The brief for a public-only session carries this:

```markdown
## Session mode: open
OEM specifications for this program are not available in this session.
If a task requires them, stop and tell the engineer to start a sealed
session — do not infer, approximate, or work around a specification you
cannot read.
```

Twenty tokens, and it turns the agent into a participant in the discipline
rather than something to be contained. It catches precisely the case where the
human misjudged the task, which is the case differential materialization alone
would leave as a confusing absence.

---

## Enforcement points, honestly ranked

1. **Human agent selection (primary, not enforced).** The real decision. Made
   with full knowledge of the task, at the only moment that knowledge exists.
2. **Differential materialization (strong for accidents).** A property of what
   exists on disk, not a claim any caller makes. An agent cannot read a file
   that was never written into its worktree.
3. **Retrieval and label correctness (strong for correctness).** Public and
   compartment labels are generated by one function for both write and filter
   paths (I-2), fail closed on absence (I-1). This is what stops the wrong
   document reaching a legitimate session; it does nothing about a session that
   goes around Caiman.
4. **Filesystem hardening (optional).** See below. Not the design; available if
   the accident rate ever justifies it.

## What does not work, and is not attempted

**Model identity cannot be verified.** A process cannot tell which model is
behind a caller. There is no attestation and no signed model identity. Any check
of the form "only allow self-hosted models" is the caller asserting its own
identity, which is not a control. Building it would produce the shape of a gate
with none of the substance, which is worse than no gate because it invites false
confidence. This is a large part of why the decision moved to the human.

**Localhost is not a boundary.** A listener on 127.0.0.1 is reachable by every
process on the host, including a frontier harness with full internet access.
This mattered when a server was in the design; it is noted here because it is
the reason a server would not have helped.

**Derived answers still carry the secret.** If a local model reads a
specification and returns a requirement, a confidential *fact* has moved even
though no confidential *document* has. This is why the rule is **no hybrid
session**: a task either touches customer material and runs entirely on the
local model, or it does not and runs normally. A "sanitized channel" that lets
customer facts reach a frontier model in derived form is the design hardest to
reason about and easiest to get quietly wrong.

That rule is unchanged from earlier drafts. What changed is that it is now
carried entirely by human discipline rather than by a mechanism. It should be
read that way, and it is stated here rather than implied to be enforced.

---

## Optional hardening

Not part of the design. Available if the accident rate ever warrants it, and
noted so the option is not rediscovered from scratch.

**Separate OS user.** Compartmented corpus materialized to a path owned by a
second uid, mode `0700`. A normal session gets `EACCES` from the kernel rather
than a refusal it could be argued out of; a sealed session runs as that uid and
its ordinary file reads simply work. Strong, and genuinely painful on macOS —
separate home directory, separate credentials, separate shell config, and
`sudo -u` for every sealed session. Give the sealed session its own worktree
rather than sharing one across two uids; shared trees mean group-writable
permissions, which is where mistakes live.

**Encrypted disk image (macOS).** `hdiutil create -encryption AES-256 -type
SPARSEBUNDLE`, mounted only for sealed work, key in Keychain. Detached, the
corpus is not merely unreadable but ciphertext. This sidesteps the multi-user
pain entirely, and "did I unmount" is a much easier discipline than "am I
running as the right user." The better option on this platform.

**Egress control.** Point a harness at a self-hosted gateway and block direct
egress to model APIs at the firewall. An existing product category — provider
selection, path blocking, and audit logging are shipped features. Relevant only
if human routing proves insufficient in practice.

## Honest limits

**This stops accidents, not a determined operator.** It always did. Even the
kernel-level options above are defeatable in minutes by someone with admin on
their own machine. That is not a weak goal: the realistic failure mode is
precisely the accidental one — six sessions in flight, one quietly pulls a
customer specification into a frontier request, and nobody notices for a week.
Making that require a deliberate act is worth real engineering. Making it
impossible is not achievable in software you control.

**Nothing stops a human pasting a specification into a chat window.** That was
always a deliberate act and always outside the threat model. It is now outside
it by design rather than by admitted limitation.

**If the requirement is genuinely "cannot leak," the control is physical:** a
machine or VM with no route to any model API. That is what air-gapped chip teams
already do. Everything else is contract plus diligence, with software raising the
friction.

---

## Conversion happens outside Caiman

Since S-08, Caiman ingests already-converted markdown. This moves a real risk
outside the system's control and it must be stated plainly.

**Handing a confidential PDF to a hosted conversion service is a disclosure, and
Caiman cannot prevent it.** By the time markdown arrives at ingest, the document
has already been wherever it was going to go. No downstream control undoes that.

This matters far more for customer specifications than for vendor manuals, for
exactly the asymmetry described at the top: a leaked reference manual is the
vendor's widely-held document, while a leaked specification is identifiable as
that customer's and covered by an agreement with them.

What Caiman does about it:

- **Provenance records the converter**, identity and version, on the artifact.
  This makes "which documents went through which converter" answerable, which is
  what you need when you discover one was hosted, or when a conversion turns out
  to have dropped content.
- **Ingest lints on a mismatch.** Ingesting a compartmented document with a
  converter identity known to be hosted should say so loudly. A lint, not a gate
  — Caiman has no reliable way to know what is hosted.

The operating rule is human: **convert compartmented documents locally.** Put it
in the ingest checklist, not in the list of enforced controls.

---

## Reclassification and revocation

Content-addressed artifacts freeze their labels with their digest. If a document
is reclassified — made compartmented when it was public, or moved into a
different compartment — pushing a new artifact does nothing about content
already materialized into live worktrees.

A **compartment correction** is the likeliest hand-entry mistake and the one with
the worst consequence: a document ingested against the wrong customer. Treat it
exactly as a reclassification.

Required:

1. **Corpus re-materialization**, so on-disk copies are removed from sessions
   that should no longer hold them. Note this cannot reach a running session's
   already-read context — only a new session is genuinely clean, and that should
   be said out loud rather than papered over.
2. **Cache eviction** for the affected digests, in every compartment cache.
3. **Brief regeneration.** A brief lists documents and shows what is available in
   the session. A stale brief will tell an agent that material is on disk and
   greppable when it is not, which is both wrong and a confusing failure to
   debug.
4. **Index purge**, if a semantic index has been built by then.

Design this while it is a paragraph. After three projects have live sessions it
is a migration.

---

## Audit

Its role has changed. It is no longer detection backing up imperfect prevention;
it is **the record that makes human routing reviewable**.

Every `sync` logs: timestamp, project and project version, agent name and
resolved profile, compartments materialized, and the document digests written.

This is cheap, deterministic, and honest in a way tool-call logging never was: it
does not depend on the agent cooperating. A log of what a server was asked
captures only the accesses that went through the server. A log of what was
materialized captures the session's entire reachable set whether or not anything
was read.

The granularity is document-level rather than line-level, and for the question
that actually gets asked — "which of our specifications did your engineers'
sessions have access to" — document-level and provably complete is a better
answer than line-level and conditional on cooperation.

---

## Test fixtures

Security behavior is specified by negative tests, using **synthetic fixtures
only**. Never commit real vendor or customer documents, not even for testing —
see `CLAUDE.md` I-3.

The sample-project plan (`DECISIONS.md` D-08) uses open hardware with freely
available specifications. The normative half has no open-source analogue and real
OEM specifications can never be committed, so it uses **synthetic specification
sets** — invented requirement IDs, a few features, a deviation document amending
a handful of requirements. Two of them, for two fictional customers, so
compartment isolation is exercised with zero NDA exposure. Synthetic is better
than borrowed here: the negative tests can assert exact behavior against content
you control.

Write these before the mechanism they test:

1. A chunk that is neither marked public nor carries a compartment is returned
   to nobody and materialized nowhere.
2. A chunk whose compartment label was lost is returned to nobody — tested
   separately from (1), because absence of a label and absence of the whole
   record fail through different paths.
3. Nothing from compartment A appears in a corpus materialized for a project in
   compartment B.
4. Syncing with an agent whose profile is `public` materializes no compartmented
   document, for any project.
5. Syncing with an agent name absent from the map fails, and materializes
   nothing at all.
6. A document carrying two compartments does not appear for a session holding
   only one of them.
7. Write-time and filter-time label generation agree, property-tested across
   generated inputs.
8. A brief generated for a project with compartmented documents contains no text
   from any document body — property-tested against generated chunk content.
9. A generated brief does not contain the customer's identity, only the program
   codename.
10. A reclassified or compartment-corrected document is gone from a
    re-materialized corpus and from every compartment cache, and the brief that
    listed it is regenerated.
11. A chunk with no resolvable locator is rejected at ingest rather than stored
    without one, and a document declared requirement-structured is rejected if
    its chunks lack requirement IDs.
12. A bare project or board name does not resolve to a version.
