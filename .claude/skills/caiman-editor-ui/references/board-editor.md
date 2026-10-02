# Board editor implementation reference

Paths are relative to the Caiman repository. Inspect current implementations;
these are reusable examples, not a requirement to inherit board domain classes.

| Source | What to reuse or study |
| --- | --- |
| `src/caiman/ui/editor.py` | Shared editor primitives: `EDITOR_CSS`, `Row.carry`, `CardRow` expansion, `add_card`, and `EditorFormApp` outer-card navigation, responsive grids, add/toggle/remove focus handling |
| `src/caiman/boards/form.py` | `BoardFormApp.compose` page hierarchy; `PartRow`, `BoardDocumentCard`, and `LinkRow` summaries and complete fields; `collect` |
| `src/caiman/configurations/project_form.py`, `project_edit.py` | The project adaptation: a boards grid, nested realized-on/governing/related rows, v1 restatement, raw-only fallback for unrepresentable shapes, and its review/register flow |
| `src/caiman/ui/cards.py` | `EditorFrame`, `DotShadow`, and `AddCardFrame`; mounted face plus decorative shadow and descendant focus handling |
| `src/caiman/ui/navigation.py` | Navigation versus text-edit modes and keyboard dispatch |
| `src/caiman/ui/theme.py` | Shared colors, field controls, action bar, and terminal theme |
| `src/caiman/boards/edit.py` | Guided form → prepare → review → explicit register; raw editing returns to form; unchanged and invalid drafts do not register |
| `src/caiman/configurations/models.py` | Target schema, document selectors, ordered values, and project/board validation |
| `src/caiman/configurations/tui.py` | JSON-array authoring flow still used by `caiman board`/`caiman project` from the CLI |

## Textual details that affect the result

- The board body starts with Board Name, Version, Board Vendor, and Notes. Its
  Board Documents, Parts, and Links sections are initially open `Collapsible`
  widgets with `.card-grid` children. This ordering illustrates the hierarchy;
  other entities choose their own fields and sections.
- Repeated containers use `height: auto`, not the default `1fr`. Grids use
  `grid-rows: auto` with row/column gutters of `1 2`; cards also use auto height.
  `resize_grids` switches one/two columns at terminal width 100.
- `CardRow` keeps `.card-editor` mounted and toggles the `expanded` class.
  `summary_data` reads draft fields for summaries without discarding partial
  input. Do not rebuild widgets from the last valid collected manifest on Done.
- A summary starts with `CardRow.heading(label, title)`, which renders the title
  with `card_heading` at `summary_width`, using the equipment label marker
  and indented wrapping. `CardRow.on_resize` recomputes that
  width (card width minus shadow margin, face border and padding, and Button line
  padding) and refreshes the summary, so the title never overflows the card.
- Repeated field widgets use classes scoped to their own row, not duplicate IDs.
  Scope collection queries to the owning section or nested record so pins from
  different levels are not mixed.
- `EditorFrame` uses an opaque `.editor-face` and a percentage-sized underlay.
  The face's right/bottom margins reserve the shadow. Fixed shadow heights can
  stop the card shrinking after collapse; parent padding can clip the dots.
- Palette: black `#000000`; solid border `#33422e`; focus `#7fdc4f`; field labels
  `#eef3e6`; text `#dfe6d3`; summary `#aab69c`; dotted shadow `#466d36`.
  Shadows use individual `⠢⠔` dots, not a dotted border or blur.
- Summary buttons have explicit left alignment and no default focus background
  that would hide the black card. Add buttons center their plus and label.
- `EditorFormApp._move_tile` compares `EditorFrame` ancestor regions, not inset summary-button
  positions. `action_vim_move` falls back to normal form focus when a grid edge
  has no card neighbour. This prevents trapping focus in a section.
- `call_after_refresh` places focus after insertion or expansion has laid out.
  The board event handler stops handled button events so nested actions do not
  accidentally trigger an ancestor action.
- `Row.carry`, `BoardFormApp.collect`, and `ProjectFormApp.collect` preserve keys the form does not own.
  Legacy board schemas and directed link shapes remain raw-edit-only instead of
  silently rewriting their data into the guided schema.

## Existing behavior checks

`tests/test_board_form.py` covers complete-field round trips, optional clearing,
lineage retention, summaries, inline expansion, add/remove, responsive grids,
keyboard escape from grids, and focus/shadow geometry. `tests/test_board_edit.py`
covers cancellation, unchanged drafts, failed preparation, raw-editor retries,
and explicit registration. Use them as examples for tests of the target editor;
assert observable behavior rather than copying board-specific expectations.
