# Embedder

## Init command
Looks in the repo for 
- target hardware
- build/test commands
- debug/deployment setup
- bench equipment/integrations
- quality rules/conventions

## What goes inside an embedder.md file
contains: generated section, commands section, and also a manual part.

under commands part, it contains
- build commnad
- serial port
- serial baudrate

---

## A real EMBEDDER.md, found in the wild

Searched GitHub 2026-09-16. This is the **only** genuine EMBEDDER.md that is
public. Copied verbatim from the public repository
`maikerlab/meatometer-zephyr` (Zephyr RTOS grill thermometer, nRF5340 + nRF7002,
94 lines, last pushed 2026-09-13):
<https://github.com/maikerlab/meatometer-zephyr/blob/main/EMBEDDER.md>

````markdown
**EMBEDDER PROJECT CONTEXT**
<OVERVIEW>
Name = meatometer
Target MCU = nRF5340 (dual-core Arm Cortex-M33) + nRF7002 Wi-Fi companion IC
Board = nrf7002dk/nrf5340/cpuapp
Toolchain = nRF Connect SDK (NCS) v3.2.3 / West / Zephyr CMake
Toolchain Path = /opt/nordic/ncs
Debug Interface = jlink (onboard SEGGER J-Link on nRF7002 DK)
RTOS / SDK = Zephyr RTOS via nRF Connect SDK
Project Summary = Wi-Fi-connected grill thermometer using MAX31855 thermocouple sensor over SPI, with SMF state machine, BLE provisioning, MQTT telemetry, and button/LED UI.
</OVERVIEW>

<COMMANDS>
# --- Build / Compile --------------------------------------------------------
build_command = west build -b nrf7002dk/nrf5340/cpuapp -p auto

# --- Flash ------------------------------------------------------------------
flash_command = west flash

# --- Debug ------------------------------------------------------------------
gdb_server_command = JLinkGDBServer -device nRF5340_xxAA_APP -if SWD -speed 4000 -port 61234
gdb_server_host = localhost
gdb_server_port = 61234
# gdb_client_command =
target_connection = remote

# --- Serial Monitor ----------------------------------------------------------
serial_port = auto
serial_baudrate = 115200
serial_monitor_command = tio {port} -b {baud}
serial_monitor_interactive = true
serial_encoding = ascii
serial_startup_commands = []
</COMMANDS>

# Project Overview

Meatometer is a Wi-Fi-connected grill thermometer built on the nRF7002 DK. It reads thermocouple temperatures via a MAX31855 SPI ADC, runs a Zephyr SMF state machine for session control (IDLE / MEASURING / ALERT), and publishes readings over MQTT. Wi-Fi credentials and broker settings are provisioned via BLE. The firmware is event-driven, with a message queue connecting button ISRs, temperature polling, connectivity events, and the state machine.

Architecture:
- `src/main.c` — entry point, initializes all subsystem interfaces and starts FSM
- `src/fsm/` — session state machine (`session_fsm.c`) using Zephyr SMF
- `src/comms/` — Wi-Fi manager, MQTT manager, BLE provisioning
- `src/hal/` — hardware abstraction (LEDs, buttons) behind `hal_iface_t` interface
- `src/sensor/` — sensor abstraction behind `sensor_iface_t` (currently `dummy.c` placeholder)
- `src/temperature.c` — temperature processing and polling thread
- `include/` — shared interfaces (`hal_iface.h`, `sensor_iface.h`, `mqtt_iface.h`, `network_iface.h`, `ble_prov_iface.h`, `app_config.h`, `app_events.h`)
- `boards/` — board-specific devicetree overlays and Kconfig

Key peripherals: SPI1 (MAX31855 thermocouple ADC on P0.06/07/26, CS P0.25), GPIOs for 2 LEDs and 2 buttons, Wi-Fi via nRF7002, BLE for provisioning.

# Bash Commands

```bash
# Build
west build -b nrf7002dk/nrf5340/cpuapp -p auto

# Build (pristine)
west build -b nrf7002dk/nrf5340/cpuapp -p always

# Flash
west flash

# Build and flash
west build -b nrf7002dk/nrf5340/cpuapp -p auto && west flash

# Menuconfig (interactive Kconfig)
west build -t menuconfig

# Clean build directory
rm -rf build

# Run unit tests (native_sim)
west test
```

# Code Style

Follow [Zephyr coding guidelines](https://docs.zephyrproject.org/latest/contribute/coding_guidelines/index.html):
- Indentation: tabs (not spaces)
- Brace style: K&R (opening brace on same line for functions, structs, control flow)
- Use Zephyr logging (`LOG_INF`, `LOG_ERR`, `LOG_DBG`) instead of `printk`
- Use Zephyr kernel APIs (`k_msgq`, `k_thread`, `k_sleep`, etc.)
- SPDX license header (`Apache-2.0`) at top of every source file
- `#pragma once` for header guards
- Snake_case for variables, functions, types; UPPER_CASE for macros and constants
- Typedef structs with `_t` suffix (e.g. `app_event_t`, `hal_iface_t`)
- Keep HAL abstracted behind interface structs (`hal_iface_t`, `sensor_iface_t`, `mqtt_iface_t`, `network_iface_t`, `ble_prov_iface_t`) for testability
- Devicetree overlays in `boards/`, never edit SDK `.dts` files
- Kconfig in `prj.conf`, board-specific overrides in `boards/<board>.conf`
- Sysbuild config in `sysbuild.conf`, per-image overrides in `sysbuild/`
- All edited `.c` and `.h` files must be formatted with `clang-format` before committing
- The project uses the Zephyr upstream `.clang-format` config in the repository root
- A pre-commit hook enforces formatting; set up with: `git config core.hooksPath hooks`
````

## Format, as confirmed by two independent sources

Two pseudo-XML blocks of `key = value`, then ordinary Markdown prose. The blocks
are what the tool generates; the prose below them is the "manual part".

`workflex-net/embedder-cli` — a third party who reverse-engineered Embedder's
installer — ships a Zod schema for the file, which types the generated core as:

- `overview`: `name`, `targetMcu`, `board?`, `toolchain`, `debugInterface`,
  `projectSummary?`
- `commands`: `buildCommand`, `flashCommand`, `serialPort`, `serialBaudrate`

The live file above carries more `<COMMANDS>` keys than the schema requires —
`gdb_server_command`, `gdb_server_host`, `gdb_server_port`, `target_connection`,
`serial_monitor_command`, `serial_monitor_interactive`, `serial_encoding`,
`serial_startup_commands` — so the set is open, not fixed.

Embedder's own docs describe a generated region delimited by
`<!-- embedder:init:start -->` / `<!-- embedder:init:end -->` so manual notes
survive regeneration. The live file does **not** contain those markers, so either
the delimiters are newer, or the author kept the content and dropped them.

## Repos and references

| Source | What it is | Why it matters |
|---|---|---|
| [`maikerlab/meatometer-zephyr`](https://github.com/maikerlab/meatometer-zephyr) | Zephyr/nRF5340 firmware with a real EMBEDDER.md at repo root | The only public specimen of the file |
| [`workflex-net/embedder-cli`](https://github.com/workflex-net/embedder-cli) | "Embedder CLI installer — reverse engineered from install.sh to TypeScript/Bun". Has `ralph/fixtures/expected/embedder-md.ts` (Zod schema), `ralph/scenarios/03-embedder-md-init.ts`, and scenarios for stlink probing, serial discovery, catalog query, document search | Independent confirmation of the format, and a list of what the CLI is expected to do |
| `ale-alfaro/dotfiles` | OpenAI Codex config with `project_doc_fallback_filenames = ["EMBEDDER.md", "TECH_STACK.md"]`, alongside a `zephyr-driver-development` skill | A working firmware engineer wiring EMBEDDER.md into a *different* agent — evidence the file is treated as portable project context |
| [docs.embedder.com](https://docs.embedder.com/core-concepts/embedder-md.md) | "Configure EMBEDDER.md" | The vendor's own description |
| [docs.embedder.com/core-concepts/schematics.md](https://docs.embedder.com/core-concepts/schematics.md) | Schematic upload | Accepts KiCad, Altium, Eagle, PADS, Xpedition, EDIF. Extracts components, pins, nets, power connections. No published schema or user-editable export |
| [docs.embedder.com/llms.txt](https://docs.embedder.com/llms.txt) | Their docs index for agents | They follow the `llms.txt` convention themselves |

Other Embedder docs worth knowing exist: `.embedderignore`, "Project memory"
(`core-concepts/memory.md`), `/peripheral` for selecting parts and supplying their
documentation, and a catalog spanning 14 named silicon vendors.

**Searches that returned nothing**, which is itself the finding: `embedder:init:start`,
`.embedderignore`, `upload-schematics`, and `serial_baudrate` + `build_command`
together. Every other GitHub match for "embedder.md" is a false positive — RAG
text-embedder documentation, or Obsidian wiki-link test fixtures.

## Findings

**Adoption is effectively zero in public.** One file, versus tens of thousands for
`AGENTS.md`. Expected for a proprietary tool used on private firmware repositories,
so read this as "the format cannot be learned from the ecosystem" rather than
"nobody uses it". It also means nobody is competing on a published board format.

**The file is mostly not about the board.** Of 94 lines, hardware description is
one sentence:

> Key peripherals: SPI1 (MAX31855 thermocouple ADC on P0.06/07/26, CS P0.25),
> GPIOs for 2 LEDs and 2 buttons, Wi-Fi via nRF7002, BLE for provisioning.

No datasheets, no document versions, no errata, no silicon revision, no schematic
reference. The only versions anywhere in the file are toolchain versions. The rest
is build, flash, debug, serial, and code style.

**Nothing in it is citable.** `CS P0.25` is asserted with no provenance. An agent
reading it either trusts the line or goes hunting; it cannot check. That is
precisely the failure mode I-5 exists to prevent, seen in a production artifact.

**The board context does not live in the file.** Embedder extracts components,
nets, pins and power topology from uploaded schematics, but none of it lands in
EMBEDDER.md — it stays inside their platform, with no published schema and no
user-editable export. Their versioning is design-revision diffing (upload a new
revision, compare components/nets/pins), not content-addressed pinning.

**Most of the file is S-01 territory.** Build, flash, GDB server, serial monitor,
bench equipment. Caiman deliberately does not model any of it, so the overlap with
a board manifest is much smaller than the name suggests.

**94 lines.** Comfortably inside the ~150-line budget the `AGENTS.md` community
converged on (`VISION.md` §4.3). A second data point for that number.

### What it means here

The competitive read stays as `VISION.md` §4 has it, but sharper: the trade is
**derived-but-opaque versus declared-but-manual**. Embedder derives board context
automatically, which is better ergonomics and is why D-04 concedes the point — but
you cannot read, diff, review, or version-control the result. Caiman declares it
explicitly, and the artifact is a file `git diff` can show you. Neither versioned
pinning, compartmentation, nor anything normative appears on their side.

For **G14**: their accepted schematic formats — KiCad, Altium, Eagle, PADS,
Xpedition, EDIF — are commercial evidence about which EDA exports actually matter,
which is the "first useful schematic export" G14 asks someone to identify.

Answering the open question in `notes.md` — *who would fill out this?* — Embedder's
answer is that the tool proposes and the human verifies: `/init` inspects the
repository and then asks the user to confirm target, commands, debug setup, bench
equipment and rules before writing the file. That is the same shape as a Caiman
importer producing a draft that a human reviews before registration, and it is
compatible with I-8.
