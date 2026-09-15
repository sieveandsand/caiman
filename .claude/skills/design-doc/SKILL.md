---
name: design-doc
description: Write or rewrite a technical document in the style of a strong internal engineering design doc — clear, detailed, rigorous, and structured for review. Use when asked to write, rewrite, restructure, or clean up a design doc, RFC, technical spec, or architecture document; when asked to make a set of docs consistent, concise, or non-duplicative; or when a document needs to be ready for an engineering design review.
---

# Engineering design documents

Produce documents a strong senior engineer would write for other engineers,
reviewers, and stakeholders: **clear enough to read quickly, detailed enough to
implement from, precise enough to review critically.**

This is a full rewrite discipline, not grammar cleanup. Reorganize when it helps.

---

## Method

1. **Read the source completely** before writing. For a rewrite, inventory every
   technical claim, constraint, number, and open question. Nothing in that
   inventory may silently disappear.
2. **Audit for duplication** if more than one document is in scope. See
   *Multi-document work*.
3. **Decide the structure** from the *Section menu*. Pick only sections that
   carry content.
4. **Write.** Lead with what a reviewer needs to decide, not with a tour of the
   system.
5. **Verify** against the *Checks* section. Run the reference validator if the
   doc set cross-references.

---

## Section menu

Use what applies. Do not include empty or generic sections to satisfy a template.

| Section | Include when |
|---|---|
| Summary | Always. What is being built, in a few sentences |
| Background / Problem | Always. Why the problem exists, and the concrete failure being prevented |
| Goals / Non-Goals | Always. Non-goals are as informative as goals |
| Requirements and Constraints | There are testable requirements or environmental limits |
| Design / Architecture | Always for a design doc |
| Detailed Design | Components have internal structure worth specifying |
| Data Flow / Control Flow | There is a sequence worth walking end to end |
| Interfaces | Other components or people depend on a contract |
| Failure Handling and Edge Cases | Almost always. Reviewers look here first |
| Security Considerations | Anything touches access, secrets, or trust |
| Performance / Resource Considerations | There are real limits or cost drivers |
| Testing and Validation | Always. Tie tests to requirement IDs |
| Alternatives Considered | Always. Include why each lost |
| Risks and Open Questions | Always. Separate the two |

### Header block

Open with orientation, not prose:

```markdown
**Status:** Proposed | Accepted | Superseded by X
**Scope:** One line on what this covers.
**Owns:** The topic this doc is authoritative for. Others reference it.
**Related:** Other documents and what they own.
```

`Owns` matters most in a doc set — it is what prevents the same topic being
restated in five places.

---

## Writing rules

**Do**

- Short and medium sentences. Active voice.
- Explain a concept in plain language before using its specialized term.
- Give the reason, not just the decision. "Rejected because X" beats "rejected".
- Use concrete numbers, paths, commands, and examples.
- Pick one term per concept and use it everywhere. Note the choice if ambiguous.
- Use tables for anything comparable: requirements, options, error conditions,
  configuration, responsibilities, trade-offs.
- Use numbered steps for sequences, workflows, and state transitions.
- Give requirements stable IDs (`R-1`, `G-2`) and cite them from tests and
  design sections. Traceability is most of what makes a doc reviewable.
- Describe complex flows so they could be turned into a diagram without further
  information.

**Do not**

- Marketing language, unnecessary adjectives, or throat-clearing.
- Vague claims: "improves performance", "provides enhanced security", "is more
  robust". Say what changes, and by how much or under what condition.
- Jargon added to sound sophisticated.
- Academic, legalistic, or bureaucratic register.
- Repeat the same information in multiple sections.
- Excessive heading depth. Three levels is usually the limit.
- Remove a technical detail to make the document shorter. Reorganize instead.

---

## Technical accuracy

**Never invent.** Not APIs, behaviors, benchmark numbers, test results, hardware
capabilities, requirements, or implementation details. Do not introduce
technologies the source material does not support.

**Never silently change a decision.** If the rewrite implies a different choice
than the source, say so explicitly and separately.

**Never drop a constraint** because it complicates the explanation.

**When the source is ambiguous or self-contradictory:**

- Preserve the intended meaning when it is obvious.
- Otherwise mark it as an open question with both readings stated.
- Never guess silently.

**When two documents contradict each other**, do not quietly pick one. Fix the
contradiction and say which document changed and why.

---

## Multi-document work

When cleaning up a set, duplication is usually the main problem and structure is
secondary.

**1. Audit first.** Find which topics appear in which files before editing
anything:

```bash
for t in "topic one|synonym" "topic two" "topic three"; do
  printf "%-40s " "${t:0:38}"
  grep -rliE "$t" --include=*.md . | tr '\n' ' '; echo
done
```

A topic in four or more files is a structural problem, not a wording problem.

**2. Assign ownership.** One document owns each topic. Everything else gets one
sentence plus a pointer. Record the assignment in each header block and in the
index (a README table).

**3. Allow duplication only for standalone entry points.** A README and an
agent-instruction file are read without the rest of the set and may restate a
compressed version. Everything else references.

**4. Keep detailed alternative analysis with the design it shaped.** A decision
log owns the record — decision, date, rationale, one line on what lost. The
design doc owns the full comparison.

---

## Checks before delivering

1. No technical detail from the source was lost.
2. No unsupported facts were introduced.
3. Terminology is consistent throughout.
4. Requirements, assumptions, constraints, and open questions are
   distinguishable from each other.
5. Every requirement ID referenced is defined, and every defined one is used.
6. Section cross-references resolve.
7. A competent engineer could implement from this without the original.
8. A reviewer can quickly answer: what are we building, why this way, what are
   the key decisions, what does it assume, what can go wrong, how are failures
   handled, what are the security implications, what are the trade-offs, what is
   still undecided.

### Reference validator

For any doc set using ID or section cross-references:

```bash
# IDs referenced but never defined, and defined but never referenced
used=$(grep -rhoE "\b(S|D|I|R|G)-[0-9]+\b" --include=*.md . | sort -u)
def=$(grep -hoE "^#+ (S|D|I|R|G)-[0-9]+" --include=*.md -r . | sed 's/^#* //' | sort -u)
echo -n "undefined: ";    comm -23 <(echo "$used") <(echo "$def") | tr '\n' ' '; echo
echo -n "unreferenced: "; comm -13 <(echo "$used") <(echo "$def") | tr '\n' ' '; echo

# Cross-document section references that point at nothing
grep -rhoE '`[A-Za-z-]+\.md` §[0-9]+(\.[0-9]+)*' --include=*.md . | sort -u |
while read -r ref; do
  f=$(echo "$ref" | sed 's/`\([^`]*\)`.*/\1/'); s=$(echo "$ref" | sed 's/.*§//')
  t=$(find . -name "$f" | head -1)
  grep -qE "^#+ ${s}[ .]" "$t" 2>/dev/null || echo "MISSING: $ref"
done
```

Renumbering sections silently breaks references. Run this after any
restructuring, not only at the end.

---

## Anti-patterns

| Symptom | Fix |
|---|---|
| Reads like a tour of the system | Lead with the decision a reviewer must make |
| "This provides better isolation" | Name the mechanism and what it prevents |
| Alternatives listed without outcomes | State why each lost, and what would change the answer |
| Failure section lists errors with no behavior | Give the behavior and the reason it is correct |
| Tests unlinked to requirements | Cite requirement IDs from the test table |
| Open questions mixed into prose | Collect them; state what each blocks and when it must be decided |
| Same topic explained in five files | Assign ownership; replace the rest with pointers |
| A trigger written as "when it becomes a problem" | Make it observable — a logged event, a threshold, a measured condition |
