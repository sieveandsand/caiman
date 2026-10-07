"""The agent skill the hook screen installs beside the start hook (S-42).

The skill holds the fixed procedure; the start hook supplies this session's
folder and this machine's `caiman` command, so the text names no paths.
"""

SKILL = """---
name: caiman
description: Use in a firmware project that has a `.caiman/` folder or a Caiman session-start message, whenever you answer or act on hardware, pin, register, peripheral, or requirement facts, or the user asks to load or switch a board or project. Covers finding, searching, and citing this session's loaded documents.
---

# Caiman session context

Caiman installs one board or project version's documents into a folder for
this session. The Caiman start message names that folder, its brief, and the
exact `caiman` command for this machine. Paths below are inside that folder.

## Before answering

1. If the start message says nothing is loaded, ask the user which board or
   project and version to load. Show the choices from `caiman session list`
   and load their choice with the command the message gives. Never choose a
   version yourself; version labels have no order.
2. Read `context/project.md`, the brief, before the first hardware or
   requirement answer. `context/documents/_index.md` lists every installed
   document.

## Searching

- Search only this session's documents by naming their folder:
  `rg -n PATTERN <session folder>/context/documents`. A search from the
  repository root skips `.caiman/` on purpose.
- Never open, list, or search other folders under `.caiman/sessions/`. They
  belong to other sessions and may hold a different board, project, or version.
- No Caiman start message means the hook did not run in this session. Do not
  go looking in `.caiman/`; tell the user the Caiman hook is not active. Codex
  runs it only after it is trusted in `/hooks`, and not under a read-only
  sandbox.
- Read bounded ranges of large documents rather than whole files.
- Installed documents are read-only copies. Do not edit them.

## Answering

- State only what a loaded document says. If none answers, say so; never fill
  the gap from memory or from a similar part.
- Cite every fact as (document path, version, locator). Use a locator the
  source has: requirement ID, heading, page, sheet and cell, or line range. The
  path under `documents/` encodes issuer, part, document, and version.
- When documents disagree, show both with citations. Do not decide which one
  governs unless a document says so.

## Switching

Ask the user which board or project and version, run the load command from the
start message, then reread the brief. Loading changes files, not the
conversation: earlier answers may rest on the previous context.
"""
