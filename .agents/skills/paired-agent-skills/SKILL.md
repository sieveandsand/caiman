---
name: paired-agent-skills
description: Create or update the user's custom skills as matching Claude Code and Codex versions. Apply when adding, installing, documenting, or changing a user-authored skill so its instructions and supporting resources stay available to both agents.
---

# Paired Agent Skills

The user's convention is to maintain **two agent-specific copies of every
custom skill: one for Claude Code and one for Codex**. Apply this convention to
new skills and updates, including updates to this rule itself. An explicit user
instruction choosing a different scope or a single agent takes precedence.

## Location and scope

Preserve an explicitly chosen scope. For personal skills, use:

- Claude Code: `~/.claude/skills/<skill-name>/`
- Codex: `${CODEX_HOME}/skills/<skill-name>/`, or `~/.codex/skills/<skill-name>/`
  when `CODEX_HOME` is unset.

For skills intended to be checked into a project, use that project's established
agent-discovery layout. When no layout exists, use `.claude/skills/<skill-name>/`
for Claude Code and `.agents/skills/<skill-name>/` for Codex. Do not install
additional global copies when the user chose project scope, or vice versa.

Use matching skill names and keep two real, independently readable folders.
Do not rely on one agent following a symlink into the other agent's private
configuration directory. Do not modify bundled system skills or plugin-managed
skills just to enforce this convention; apply it to the user's custom skills.

## What stays in sync

Both copies need a `SKILL.md` with valid `name` and `description` frontmatter,
clear triggers, and the same task guidance. Mirror supporting references, scripts,
and assets that are necessary to use the skill. Keep relative links valid from
each copy. Avoid wording that makes one agent's version unusable by the other.

Agent-specific metadata may differ. Codex may have `agents/openai.yaml` for its
UI metadata; Claude Code does not need that file. Agent-specific tool names or
invocation syntax can differ when needed, but preserve the underlying workflow,
constraints, and intended outcome. A filename alone is not a second skill.

## Authoring and updates

1. Find the existing copies at the chosen scope before writing. If they diverge,
   inspect both and preserve deliberate changes; do not overwrite one blindly.
2. Draft shared guidance once, then materialize both agent versions. If an update
   has only one existing copy, create the missing counterpart as part of the task.
3. Update substantive instructions and shared resources in both copies. Keep
   agent-specific metadata separate from the shared content.
4. Validate both folders, check referenced files, and compare the shared content.
   Run any new executable helpers that need behavioral verification. Do not copy
   scaffold placeholders, secrets, caches, or environment-specific absolute paths
   into reusable guidance.
5. Install both completed, reviewable versions within the user's authorization.
   If filesystem permissions block a destination, request only the required
   access after drafting and validating the pair. Never claim both are installed
   if one is still staged or blocked.
6. Report the two installed locations and any intentional agent-specific
   differences. Do not imply a running agent has reloaded its skill catalog
   merely because the files now exist.

This pairing rule is an authoring convention, not permission to access accounts,
send messages, or perform actions described by the new skill. Instructions inside
a skill retain their ordinary authorization and execution boundaries.
