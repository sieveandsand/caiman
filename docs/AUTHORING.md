# Board and project configuration

The TUI and editable JSON files use the same draft model and validation rules.
Registration stores a complete, immutable snapshot. Document and board references
resolve to digests before review; registration verifies those pins again without
following updated tags. This implements S-28.

## Compartments

A **compartment** is a confidentiality boundary. Usually, create one per
customer, such as `oem-alpha`. Public documents need no compartment. For private
documents, a project must include **every** compartment assigned to the document.
Add a separate project compartment only when some information needs tighter
sharing.

The same word is used everywhere: the TUI, the config keys `compartments` and
`compartment`, the CLI flag `--compartment`, error messages, and the architecture
and storage documents.

## Launch

```bash
caiman
```

Caiman opens the home screen. There is no default board or project: every action
that works on one asks which, each time. **Create board** takes the board's
identity, version, and first hardware part. **Create project** takes the codename,
version, customer, compartments, and specification set, and you choose the
registered board version it uses. Review before registering. Manuals and
specifications can be added later: the initial document lists may be empty.

`caiman ingest manual.md` opens the document form directly. The compartments of
projects you explicitly choose are remembered locally, so project lists can
include them next time; you can enter additional compartments to find other
projects. Caiman never discovers private projects by scanning undeclared
compartments, and it never remembers which board or project you used. This
preference does not select an agent session mode.

During ingestion, choose an existing project or board and its part to reuse
declared metadata. You can create a new board or project from the same flow and
return to the document form without losing entered values. Program and
compartment information come from the selected project; issuer and part identity
come from the selected board part. A project's customer name is context, not an
assumed document publisher identifier. Manual identity entry is also available.
Always explicitly choose and review document access before registration.

Selecting a configuration supplies metadata; it does not add the new document to
an existing immutable snapshot. Use the configuration editor to adopt its digest
into the board or project's document set. See S-29 for the setup decision.

## Open a configuration editor directly

```bash
caiman board configure
caiman project configure
```

Enter the top-level fields in the form. Edit parts and links (boards), or
documents, precedence, and features (projects), in the JSON collection editors.
Use **Refresh catalog** to see registered documents and copy exact references or
digest pins. A board sees public documents; a project catalog uses the explicitly
entered compartments in addition to public documents.

Select **Review**, inspect the identities, compartments, resolved pins, and
declared relationships, then **Register**. **Back to edit** invalidates the
previous review. Cancellation before registration writes nothing to the store.
The complete resolved JSON is available in an expandable review panel.

The home screen is the primary human interface. Its grid offers document
ingestion and browsing, and for boards and projects just two tiles each:
**Create** and **View**. Editing starts from what you are viewing: press **e**
on a board card, or on a project snapshot after choosing it. JSON import, export,
validation, and templates are available as direct commands (below), which also
serve scripts and agent tooling; interactive commands still require a terminal.
Home tiles are drawn with the same dotted border as board cards.

### Keyboard navigation

On the dashboard, **h/j/k/l** move left/down/up/right; **Enter** opens the tile,
and **q** quits.
In forms, **h/k** move to the previous control and **j/l** to the next.
**Enter** or **i** starts editing a text field; **Escape** returns to navigation.
While editing, letters including `hjkl` are ordinary text. Clicking a text field
also starts editing. The mode hint beneath the form shows the available keys.
In navigation mode, **q** returns to the parent menu using the form's cancel/close
action. It closes an open dropdown first. While editing, **q** types normally;
press Escape first to use it for navigation. Leaving a form does not register
unsubmitted changes, and cannot interrupt a registration already being written.
In dropdown menus, **j/k** move through choices, **Enter/l** selects, and
**Escape/h** closes the menu. Tab and Shift+Tab also move between controls.
These keys are the whole scheme: there are no Ctrl shortcuts, and the only prompt
at the bottom of each screen is the mode hint.

The shared terminal theme takes its colours from a real caiman: a pure black
canvas, bright green accents, and muted reed-coloured secondary text. Fields are
clearly outlined, with a subtle fill and a green border when focused. Labels sit
directly above their fields, and a divider separates the form from its navigation
buttons.

The home screen's top-right corner shows a solid green pixel-art caiman with a
raised eye, a smile, and four legs mid-stride. It is drawn with half-block
characters, two square pixels per cell, and hides when the terminal is too narrow
or too short to fit it without crowding the tiles.

A future native macOS app can reuse the same core without importing terminal
widgets.

## Work with a config file

```bash
caiman board template --output .caiman/board.json
caiman project template --output .caiman/project.json
```

Fill out the JSON draft in an editor, then validate or open it in the TUI:

```bash
caiman board validate .caiman/board.json
caiman board configure .caiman/board.json
caiman project validate .caiman/project.json
caiman project configure .caiman/project.json
```

`validate` checks the draft and resolves pins without writing a version. It prints
the resolved configuration. `configure` loads the draft into the form and requires
review before registration; it does not modify the source config file. Duplicate
JSON keys, unknown fields, and invalid relationships are errors rather than being
silently discarded.

Templates are intentionally incomplete drafts. They must be filled in before
validation succeeds. Template/export files are created with mode `0600`, and an
existing file is never overwritten. `.caiman/` is gitignored; keep private project
drafts there or outside the firmware repository.

Every store-backed command accepts `--store /absolute/path/to/store`. Without
it, the normal Caiman store configuration applies. Nothing here commits or pushes.

## Board fields

| Field | Meaning |
|---|---|
| `board`, `version` | Board identifier and opaque version label |
| `parts` | Nonempty list of parts identified by unique `role` |
| `parts[].part` | Document-compatible part identity, `issuer/part` |
| `parts[].documents` | Document selectors; may be empty when no documents have been selected |
| `silicon_revision`, `refdes` on a part | Optional declared silicon revision and schematic reference |
| `links` | Named links using either `between` or `from`/`to` endpoints |
| `derives_from`, `relation` | Optional pair: predecessor label and human explanation |

Endpoints name a declared role or `role.PERIPHERAL`. A part's document must match
its issuer/part identity. If both document applicability and a part's silicon
revision are supplied, they must agree; Caiman does not infer missing revisions.
Boards contain no customer or project fields and may pin only public documents.

## Project fields

| Field | Meaning |
|---|---|
| `project`, `version` | Program codename and opaque version label |
| `customer`, `compartments` | Customer identity and a nonempty set of compartments (usually one per customer) |
| `board` | Explicit board `name` and `version`, with an optional existing `digest` pin |
| `spec_set` | Human-declared frozen specification release |
| `documents` | Selected specification documents |
| `precedence` | Document selectors in human-declared governing order; optional `note` |
| `features` | Named features with `scope` of `required` or `not-used` |
| `features[].governed_by` | Selected document references, optionally with requirement-ID strings |
| `features[].realized_on` | Roles that exist on the pinned board |
| `features[].related` | Existing feature names paired with a human-written `relation` |
| `derives_from`, `relation` | Optional predecessor and explanation |

Feature governing documents must belong to the project's documents or precedence
set. Requirement IDs and ranges are preserved as declarations, not expanded or
interpreted as obligations by Caiman. Precedence is preserved, not inferred, and
feature implementation status is not tracked.

A document's complete compartment set must be included in the project's set.
Project manifests remain in their named compartments; they never enter the public
store. Public board manifests can be shared by multiple customer projects.

## Document selectors

List exact available selectors with:

```bash
caiman documents
caiman documents --compartment example-customer
```

For example, after registering the README's synthetic manual:

```json
{
  "ref": "example/example-mcu/reference-manual/Rev%20A",
  "compartment": "public"
}
```

Alternatively, supply a full `sha256:…` manifest digest. If both `ref` and
`digest` are present, the digest is authoritative; the ref is diagnostic metadata.
References use the encoded paths shown by the catalog, so opaque labels with
spaces or slashes cannot become filesystem traversal.

Review resolves a selector into `digest` and `compartment`. Ambiguous references
require an explicit compartment or digest. Feature selectors bind to the already
selected project pins. Loading or registering a prepared snapshot never silently
adopts a newer document or board revision.

## Inspect, export, and derive versions

### Board cards and Vim editing

**View boards** opens a grid of registered board versions, each card drawn with
a dotted border. A card gives the board name, its version, the store digest, and
the complete parts list. Each part takes two lines: its role and part number,
then its declared silicon revision, schematic reference, and document count. No
card is marked as current, because there is no default board. Narrow terminals
use one column; Page Up/Down scroll cards with long parts lists.

Use `hjkl` to select a card and **Enter** or **e** to open its JSON configuration
in Vim. Caiman releases the terminal while Vim is running. Edit the temporary
draft and use **`:wq`** to return to Caiman for validation and a changes review.
**Register changes** writes the reviewed snapshot; **Edit in Vim** reopens the
same draft. Invalid JSON or configuration data can be corrected without losing
the edited text. Use **`:cq`** to cancel Vim editing, or **q** from the Caiman
review to discard the draft and return to the board grid.

Vim must be installed on `PATH`. The editor receives a temporary copy, never a
stored object. Updating the same name/version repoints that label only after
review; existing project digest pins keep their original board. To save a new
version, edit the version label and declare any desired lineage in the draft.

### Configuration forms and direct commands

To edit a project, open **View projects**, choose one, and press **e** (or select
**Edit**) on its snapshot. Boards are edited from the board grid in Vim, as
described above. In the project form, either choose a new version label and
explain how it relates to the previous version, or explicitly replace the
selected version's ref. The editor opens the complete snapshot, including its
existing digest pins; review the changes before registering. Editing a board
does not adopt it into an existing project; edit the project separately when you
want that.

```bash
caiman board show example-board
caiman board show example-board --version 'Rev A'
caiman board export example-board --version 'Rev A' --output .caiman/exported-board.json
caiman board new-version example-board --from-version 'Rev A' --version 'Rev B' \
  --relation 'Adds a second serial peripheral'
```

Omitting the version on `show` lists labels; it never chooses a latest version.
`new-version` starts the TUI with a complete copy of the selected snapshot and
the supplied lineage. Existing pins carry forward until explicitly edited. The
old snapshot remains resolvable after registration.

Project reads require explicit compartments; repeat `--compartment` when the
project requires multiple compartments:

```bash
caiman project show example-program --version Prototype --compartment example-customer
caiman project export example-program --version Prototype \
  --compartment example-customer --output .caiman/exported-project.json
```

The same `new-version` flow works for projects. Human version labels are mutable
refs: registering the same name/version can repoint that ref, but cannot change
previous digest-pinned snapshots.

## Current limits

This slice registers and inspects configuration; it does not materialize session
workspaces, generate briefs, synchronize Git remotes, or automate cascaded
document adoption. Nested editing currently uses JSON collections rather than a
dedicated row editor for every domain object. Multi-compartment publication is
atomic per ref, not an all-or-nothing transaction across compartments. Local
access checks assume an authorized caller; they are not process isolation.
