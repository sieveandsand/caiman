# Describing a board in an AGENTS.md

Historical research. These observations are not implementation requirements;
[S-31](../DECISIONS.md#s-31-the-board-schema-is-caimanboardv2-schema-literals-are-a-table)
records the adopted board design. Recheck external claims before relying on them.

Prior art: people hand-writing hardware context into agent context files, which
is the thing Caiman generates. Searched GitHub 2026-09-16 via `gh api search/code`.

**Re-run before relying on this.** Queries used, so it is reproducible:

    gh api -X GET search/code -f q="datasheet filename:AGENTS.md"
    gh api -X GET search/code -f q="pinout filename:AGENTS.md"
    gh api -X GET search/code -f q='"board revision" filename:AGENTS.md'
    gh api -X GET search/code -f q='"silicon revision" filename:AGENTS.md'

**Read in full:** `OpenDrone-hw/OpenESC-20x20`, `OpenDrone-hw/KiCad-Library`,
`DavidClawson/OpenScope-2C53T`, `hlord2000/nordic-lib-kicad`. Everything else
below appeared in search results only and its contents were **not** inspected —
do not characterise those without opening them.

## How common is it

| Query | Total hits |
|---|---|
| `datasheet filename:CLAUDE.md` | 974 |
| `datasheet filename:AGENTS.md` | 565 |
| `errata filename:CLAUDE.md` | 564 |
| `errata filename:AGENTS.md` | 413 |
| `pinout filename:AGENTS.md` | 323 |
| `"board revision" filename:AGENTS.md` | 46 |
| `"silicon revision" filename:AGENTS.md` | **4** |

Counts include incidental mentions — "errata" hits are mostly documentation
projects — so this is a gradient, not a census. The gradient is the finding:
hundreds of people put datasheets into agent context, dozens name a board
revision, four mention silicon revision, and none of those four turned out to be
board descriptions. **Revision applicability and errata are effectively absent
from the practice.**

## OpenDrone-hw — the closest thing to Caiman found anywhere

An open-hardware org (<https://github.com/OpenDrone-hw>) with roughly twelve
board repositories — ESCs, flight controllers, ELRS receivers, a VTX, Remote ID —
each carrying an `AGENTS.md`, plus a shared `KiCad-Library`.

### A board identity table

From [`OpenESC-20x20/AGENTS.md`](https://github.com/OpenDrone-hw/OpenESC-20x20),
a `## Repo` table with: maintainer, status, KiCad version, KiCad project file,
root schematic, board file with stackup ("6 layers, 1.6 mm, 2 oz outer copper"),
QC and flashing fixtures, local library, shared library submodule, design rules,
fab config, board setup, and license. Plus a warning that the project is named
`4in1-mini`, not after the repo, and renaming breaks fab archives, release assets
and website board art.

### An agent permission boundary

Quoted verbatim:

> **Metadata yes, connections no.** An agent may write BOM and documentation
> fields (MPN, Manufacturer, LCSC, Cost, Datasheet, text variables). An agent may
> not change nets, wiring, routing, placement, footprint assignment, or any value
> that changes the circuit.

Also: *"**Never text-edit** `.kicad_sch`, `.kicad_pcb` or `.kicad_dru`"*, and
*"**Reuse before you draw** … its symbol links to the exact committed datasheet"*.

The rules block is marked *"Identical in every OpenDrone board repo. Do not edit
here; edit the template."* — a hand-maintained version of the cascade.

### A content-addressed datasheet manifest

The single most relevant artifact found. `KiCad-Library` is consumed by each board
as a **pinned git submodule**, and its rule is that *"every orderable physical
symbol must map to one exact PDF in `datasheet/manifest.json`"*. That file
(12.5 KB, ~112 parts) looks like:

```json
{
  "version": 1,
  "documents": {
    "AT32F421.pdf": {
      "symbols": ["AT32F421G8U7"],
      "source_url": "https://www.arterychip.com/download/DS/DS_AT32F421_V2.03_EN.pdf",
      "sha256": "953409957662e1fe4fada766411913ca832382551500f20fad474dec0739c0de"
    },
    "BMI270.pdf": {
      "symbols": ["BMI270"],
      "source_url": "…",
      "sha256": "…"
    }
  }
}
```

The PDFs themselves are committed under `datasheet/`.

`PARTS-USED.md` is generated (`python3 tools/build-parts-index.py`) with a
declared inclusion rule: a part is listed only if it is on a board at
`status-alpha` or beyond, meaning *"it has been through a real assembly run:
sourced, footprinted, and it survived a reflow oven."* 112 parts across 8
manufactured boards.

## DavidClawson/OpenScope-2C53T — the most Caiman-shaped content

Reverse engineering of an FNIRSI 2C53T oscilloscope, so provenance matters to the
author and they invented notation for it.

- `## Hardware Target` lists parts **by role**: MCU, LCD, FPGA, SPI Flash, DAC,
  Buttons, Touch — the same move as S-12.
- **`Board revision: 2C53T-V1.4`** as an explicit field.
- A `### Confirmed Pin Assignments` table, columns Function | Pin | Notes.
- Hand-rolled confidence and provenance markers, because nothing supplies them:
  *"15/15 hardware-confirmed"*, *"likely GT911/GT915"*, *"not yet mapped to MCU
  pins"*, and *"Originally identified as GD32F307 from firmware analysis; physical
  teardown revealed AT32 (markings sanded off)"*.

## hlord2000/nordic-lib-kicad

An `AGENTS.md` that is a per-family symbol-layout convention guide for Nordic
parts — which edge each pin class sits on, how NFC pairs are placed per family,
where decoupling pins go on nRF52 vs nRF53 vs nRF54L. Explicitly *"based on direct
parsing of the KiCad S-expression files, not on `kiutils`."* Descriptive hardware
knowledge as agent context, at library rather than board level.

## Other hits, not inspected

Listed for follow-up only; contents unknown.

- Hardware-looking: `OpenDrone-hw/OpenFC-Lite-Mini`, `laurb9/StepperDriver`,
  `thelastoutpostworkshop/esp-pinout-explorer`, `xbst/PinConnect`,
  `dkyazzentwatwa/WireTap-32`, `michaelkamprath/minimal-64x4-expansion-cards`,
  `Faradworks/Pinscope`, `jamro/tiny-engineer`, `kaluma-project/kaluma`
- `K-Dense-AI/scientific-agents` has an `fpga-engineer/AGENTS.md`
- `Seeed-Projects/Seeed-Jetson-DevelopTool` has `skills/codex/imx477-a603-setup/AGENTS.md`
- Large projects where the mention is probably incidental: `tinygo-org/tinygo`,
  `hathach/tinyusb`
- The four "silicon revision" hits — `fabkury/p3a`, `ymei/STM32TMrdo`,
  `habedi/microcontroller-playground`, `jmoles/dotfiles` — none looked like board
  descriptions from their paths

## Findings

**The demand is real and practitioners rebuild the model by hand.** OpenDrone
independently invented a sha256-pinned datasheet manifest, an agent-edit boundary,
and template-shared rules across board repos. Nobody does that for fun; they did
it because the problem bit them. This is the strongest available evidence that
I-4 and document pinning solve something felt rather than something imagined.

**Two invariants were independently reproduced.** "Metadata yes, connections no"
is I-8's declared-not-inferred line. The pinned submodule plus digest manifest is
I-4. Neither project has read a word of Caiman's design.

**Provenance gets reinvented badly when it is not supplied.** OpenScope's
"hardware-confirmed" / "likely" / "not yet mapped" markers are an ad-hoc
confidence scheme. They exist because the format gives the author nowhere to say
where a fact came from — the problem I-5 exists to solve, visible in the wild.

**What is still missing everywhere:**

- **Document versions as a field.** OpenDrone comes closest and still buries
  `V2.03` inside a `source_url` string, so nothing can compare or pin a version.
- **Citation locators.** These are PDFs. No heading paths, no requirement IDs; an
  agent cannot cite a claim back to a place in a document (I-5).
- **Silicon-revision applicability.** Four mentions on all of GitHub.
- **Compartments.** Every example is open hardware, so nobody has the NDA problem
  Caiman is built around.
- **Anything normative.** No specification set, no program freeze, no precedence,
  no deviations.

### One idea worth considering

OpenDrone binds a datasheet to a **part in a shared library**, reused by every
board that places that part. Caiman binds documents to a **part instance on a
board**. Theirs avoids restating one pin across eight boards; ours is what makes
`silicon_revision` applicability checkable at all, since applicability is a
property of the instance and its revision, not of the part in the abstract.

Not a proposed change. Worth recording in `DECISIONS.md` D-13 as a considered
alternative with that reason, so it is not rediscovered later.
