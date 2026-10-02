---
name: caiman-editor-ui
description: Build or adapt entity edit views using Caiman's guided board editor layout, with top-level fields, collapsible card grids, inline editors, add cards, and a separate review/save flow. Use when applying the board edit experience to projects or other entities, or maintaining that editor pattern; use caiman-card-ui for gallery cards alone.
---

# Caiman Editor UI

Use the established board edit experience as the reference for guided editing.
Adapt its structure and interactions to the target entity's schema. Applying this
skill does not itself authorize changing another view or registering any data.

## Page layout

Keep a short `caiman / edit <entity>` brand above one vertically scrolling body.
Place the entity's scalar identity and metadata fields first, then its repeated
collections in named, initially open collapsible sections. Each section contains
a responsive card grid with a matching add card at the end, even when empty.
Use meaningful section counts; distinguish stored counts from live draft counts.

Keep validation feedback and the action bar outside the scrolling body. The main
action is `Review changes`, followed by the existing raw-editor escape hatch if
one exists, and `Back to <collection>`. Keep a compact keyboard hint visible.
Do not add a raw editor to unrelated products merely to copy the board page.

Use concise, bright, bold Title Case field labels with vertical breathing room.
Put essential input-format cues in placeholders. Keep explanatory subtitles and
implementation commentary out of the ordinary edit path; retain actual errors
and explanations for unsupported or read-only records.

## Editor cards

Title each editor card with the same bold fullwidth heading as gallery cards,
falling back to the exact value in bold ordinary text when it does not fit the
card's width or has an unsupported character; keep the rest of the summary in
compact ordinary text. Use a black
face, solid muted-green outline, pale identity, subdued summary facts, green
accents, and a discrete dotted focus shadow. Left-align summaries. Center a large
`+` and short action label on add cards.

Summaries show the recognizable identity and only the facts needed to select a
record. Keep verbose notes, aliases, digests, and other details in the expanded
fields. Omitted summary information must remain editable and preserved.

Click or Enter on a summary expands its fields **in place**, focusing the first
field. Keep complete draft state when collapsing, including incomplete or
currently invalid input. `Done` updates the summary, collapses the editor, and
returns focus to its summary; it does not save, register, or validate the whole
entity. Do not require successful parsing merely to display a collapsed summary.

The add card inserts a blank expanded record immediately before itself and
focuses its first field. Keep the add card last after every insertion. Removing a
record returns focus to a useful surviving control, normally the section's add
card, without changing sibling drafts. Small repeated fields inside an expanded
card can remain simple rows with local add/remove buttons, as document pins do
inside board parts; avoid unnecessary grids inside grids.

## Geometry and navigation

Use two columns when the terminal is wide enough and one on narrow screens; the
current board editor switches at 100 columns. Size sections and cards to content,
align row tops, and let only the expanded card grow. A taller row must not stretch
its collapsed neighbour's face. Reserve the shadow's right column and bottom row
in both focus states so focus alone never moves cards.

Use the existing navigation/edit modes: hjkl moves among controls, Enter opens a
card, Enter/i starts typing in a field, Escape returns to navigation, Tab advances,
and q goes back outside text-edit mode. Horizontal card navigation compares outer
card row tops, including add cards. Skip collapsed descendants and allow movement
out of a grid to surrounding form controls. Focusing fields inside a card keeps
that card's dotted shadow active; it disappears when focus leaves the card.

## Draft and save semantics

Keep the original snapshot separate from the working draft. Collect edits by
copying the draft and replacing only fields owned by the form. Preserve unrendered
fields, lineage, opaque versions, selectors, access labels, and existing pins.
Respect the target schema's distinction between clearing an optional value and
retaining required fields or empty collections. Completion suggestions help type
values; they must not silently normalize or restrict declared values.

Prepare and validate before the existing review/save stage. Validation errors
retain the draft and expose the relevant field when possible. Back/cancel does
not write. Review shows meaningful changes before the explicit register/save
operation. For Caiman, keep immutable digest pins intact when a version label is
updated and preserve existing new-version/lineage rules.

If a raw editor already exists, pass it the full current draft and return its
result to the guided form before review. Preserve drafts through retries and
abandonment according to the existing workflow. Unsupported schemas or shapes
must not be silently migrated or stripped to fit the guided form; explain the
limitation and retain the supported fallback.

## Apply to another entity

Inspect its schema, current editor, and save workflow before choosing sections.
Map scalar fields to the top form and repeated records to section grids; do not
copy board parts, links, or public-only document rules into unrelated entities.
For a project, the mapping is identity/customer/access/spec-set fields at the
top and boards, documents, and features below. Inspect their real shapes first:
board selectors must retain their pinned identity, each realized part names its
board and version, and document access must follow project compartments.
Preserve existing fields and editing capabilities while changing presentation.

For implementation in this Textual repository, read
[Board editor reference](references/board-editor.md). Reuse the shared card
primitives; the sibling `caiman-card-ui` skill provides additional visual details
when needed. This skill's editor instructions remain usable on their own.

## Verify the adaptation

Check untouched-draft round trips, preservation of hidden fields and pins,
collapse/reopen with incomplete input, add/remove focus, sibling independence,
empty sections, unequal heights, narrow/wide resizing, scrolling, and focus shadow
transitions. Verify navigation can leave grids and typing does not trigger it.
Exercise validation/re-edit, cancel without writes, and explicit registration
through the target's existing workflow. Inspect the rendered terminal when
changing visual geometry; headless checks cannot establish font appearance.
