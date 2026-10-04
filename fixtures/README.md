# Firmware projects

These are working Caiman example datasets: hardware models, real application
source, integration notes, and clearly identified example acceptance criteria.
They support onboarding, manual UI exploration, local demo data, and integration
tests. Most unit tests still construct their own small synthetic inputs.

The dataset uses `caiman.examples.v2`, explicit `pod` routes, and current board
and project schemas. Document manifests are generated at import as
`caiman.document.v4`, with a fresh stable ID, a null initial `previous`, and a
current-manifest pointer. Resolved attachments use `{pod, document, blob}`.
The fixture loader does not upgrade older installed datasets or import overlays.

## What is included

| Application | Board snapshot | Why it is useful |
|---|---|---|
| Zephyr micro:bit sound, R1 | `bbc-microbit`, `v1.3` | nRF51822, MMA8653FC, multiplexed display, buttons, external piezo |
| Zephyr micro:bit sound, R2 | `bbc-microbit`, `v2-zephyr-lsm303agr` | nRF52833, LSM303AGR, changed pin mapping, built-in speaker |
| Adafruit MacroPad HID | `macropad-rp2040`, `circuitpython-9.2.8` | Keys, USB keyboard/consumer control, encoder, mouse |
| Adafruit MacroPad tone keypad | Same MacroPad snapshot | Same hardware, different feature scope: monophonic audio and key lighting |

There are **11 public documents, 3 board snapshots, 4 project snapshots, and
2 document collections**. The MacroPad version names the firmware definition
used to model it, not a claimed PCB revision. The micro:bit v2 model selects the
LSM303AGR population in the pinned Zephyr target; it does not describe every
v2 production variant. Assembly identifiers such as `buttons-a-b` and
`speaker-assembly` are explicitly described as assemblies, not chip MPNs.

`board.json` and `project.json` are convenience copies of the micro:bit v2/R2
drafts. The historical `reference-manual.md` path now contains the v2 integration
notes, **not a semiconductor reference manual**. `customer-specification.md`
contains the Caiman-authored sound R1 baseline, **not a customer document**.
Canonical files live in `boards/`, `projects/`, and `documents/`; the loader
reads those paths from `dataset.json` and does not import the copies twice.

## Load into Caiman

From the checkout, with its Python environment installed:

```bash
.venv/bin/python scripts/load_examples.py --check
.venv/bin/python scripts/load_examples.py --install
.venv/bin/caiman
```

Use `--store /absolute/path/to/store` with either loader command to override the
normal Caiman config/XDG store selection. For example:

```bash
.venv/bin/python scripts/load_examples.py --install --store /tmp/caiman-demo/store
.venv/bin/caiman --store /tmp/caiman-demo/store
```

The default/check mode writes only to a disposable temporary store. It validates
source hashes, document admission, selectors, feature/part relationships, and
the complete document → board → project graph, then checks destination conflicts.
Installation uses Caiman's existing preparation and registration services.
It needs no network access, firmware SDK, device, remote repository, or push.

Repeated installation preserves digests and is a no-op. A differing existing
document, board, project, or collection at the same identity stops the import
before any destination writes. The loader does not delete, rename, or repair
existing unrelated entries. Use a new fixture version to publish changed data;
do not overwrite a previously imported release silently.

Close other Caiman writers while importing. As with normal registration, the
store has no transaction spanning the entire dataset. If an I/O failure
interrupts installation, rerun it: complete matching entries are reused.
The loader verifies all imported pins again after writing.

Installation creates `demo-microbit` and `demo-macropad` pods so their projects
appear in the gallery. Existing preferences are
retained, and the previous state file is backed up under
`<store>/.example-import-backups/` before modification. Neither a board nor a
project becomes a default. All example documents live in the **public** pod;
projects live in their named demo pods.

## Explore the examples

1. Open **Boards** and compare the two `bbc-microbit` snapshots. Edge connector
   P0 is MCU P0.03 on v1 and P0.02 on v2; v2 sound instead uses PWM1 on P0.00.
   The integration notes carry the exact source definitions and pinctrl.
2. Open **Projects** and compare `microbit-sound` R1-v1.3 with R2-v2. R2 retains
   the R1 baseline and explicitly adds an amendment to requirements 001 and 004.
   R1's board and document pins remain unchanged.
3. Compare `macropad-hid` and `macropad-tone`. Both pin the same board digest.
   Speaker audio is outside the HID example's scope and required for tone.
   The tone example stops on *any* key release, even if another key stays down.
4. Open **Documents** for the two source/acceptance collections. Each source
   document includes immutable upstream URLs, per-file hashes, original source
   copyright headers, and full applicable license notices.

Useful CLI reads:

```bash
.venv/bin/caiman board show bbc-microbit --version v1.3
.venv/bin/caiman project show microbit-sound --version R2-v2 --compartment demo-microbit
.venv/bin/caiman project show macropad-hid --version R1 --compartment demo-macropad
.venv/bin/caiman documents
```

The acceptance documents propose checks; importing them does not execute those
checks or establish compliance. Firmware builds, electrical tests, and real
device validation have not been performed for these fixtures.

## Provenance and redistribution

| Upstream | Pinned version | Included material and license |
|---|---|---|
| [Zephyr](https://github.com/zephyrproject-rtos/zephyr/tree/413b789deb391d3a37d06b463288a5fe765ee57e) | v4.2.0, `413b789deb391d3a37d06b463288a5fe765ee57e` | Board descriptions, devicetrees, pinctrl, sound sample and overlays; Apache-2.0 |
| [CircuitPython](https://github.com/adafruit/circuitpython/tree/361dbc02066f8d2b83c3a7f1f4993a9a590d1239) | 9.2.8, `361dbc02066f8d2b83c3a7f1f4993a9a590d1239` | MacroPad board initialization, pins and config; MIT, with Scott Shawcroft/Adafruit notices in source |
| [Adafruit MacroPad](https://github.com/adafruit/Adafruit_CircuitPython_MacroPad/tree/c3b6a690fa71af3bd39cfd157ea812e6e5d950ea) | `c3b6a690fa71af3bd39cfd157ea812e6e5d950ea` | Helper library: MIT; keyboard/mouse and tone example files: **Unlicense**, per their SPDX headers |

License texts are under `licenses/` and embedded in the source documents so
attribution survives standalone document ingestion. Original upstream files
are reproduced unmodified in fenced blocks; the introductions and Markdown
wrappers are additions by Caiman. `sources.lock.json` records the repository,
commit, path, file-level license, and byte hash of every included source block.
It also preserves whether the upstream file ended with a newline.

These permissions cover the selected software/documentation files, not a blanket
license to redistribute manufacturer PDFs, third-party dependencies, hardware
CAD, or trademarks. No such PDFs, dependency trees, or hardware CAD are bundled.
The integration notes do not invent register maps, component tolerances, or
silicon revisions absent from the cited source. All feature requirement IDs,
acceptance baselines, and the R2 deviation were authored for Caiman and are
clearly distinguished from the upstream material.

## Maintain and validate

Update canonical files and `dataset.json` together. If changing a source block,
fetch an explicitly selected upstream commit, review the file's own license,
retain its copyright and notices, and update its entry in `sources.lock.json`.
Keep the four historical convenience files synchronized with their canonical
counterparts. Do not infer a hardware revision or a requirement from a new tag.

```bash
.venv/bin/python -m pytest tests/test_examples.py
.venv/bin/python scripts/load_examples.py --check --store /tmp/caiman-fresh-check/store
```

Tests check the complete graph, governing requirement IDs, shared board pins,
release separation, idempotence, preservation of unrelated data/preferences,
and conflict refusal without partial writes. Ordinary unit-test synthetic
documents remain useful for focused validation and compartment-isolation tests.
