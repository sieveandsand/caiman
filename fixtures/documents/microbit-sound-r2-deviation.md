# micro:bit sound R2 hardware deviation

These are Caiman-authored example acceptance criteria derived from the linked
upstream application. They are not an upstream specification, a customer
contract, or evidence of hardware validation. Requirement IDs and release names
are local to this dataset. This document is public; the project compartment is
only an example grouping. Acceptance checks below are proposed, not executed.

## Explicit relationship to R1

R2 includes the complete R1 document plus this explicitly authored amendment.
Only REQ-SOUND-001 and REQ-SOUND-004 are amended below; REQ-SOUND-002 and
REQ-SOUND-003 are retained unchanged. This statement is document content, not
an automatically inferred precedence rule or an upstream Zephyr release.

## Integrated sound target

REQ-SOUND-001: For R2, replace the R1 hardware selection with the pinned micro:bit
v2 LSM303AGR model. Use the built-in speaker through PWM1 channel 0 on P0.00,
including the source pinctrl inversion. Do not use the v1 external P0 route.
Check the v2 board pin table and overlay together before building.

## Accessory removal

REQ-SOUND-004: For R2, no external piezo shall be required for acceptance. Keep
sensors and Bluetooth outside application scope and retain the source startup
beep behavior. Run the tone and busy checks with only the board's built-in speaker.

## Traceability

Basis: Zephyr v4.2.0 `bbc_microbit_v2.dts`, `bbc_microbit_v2-pinctrl.dtsi`,
`sound/boards/bbc_microbit_v2.overlay`, and the sound README. The R1 project
continues pinning its own hardware and document set after R2 is imported.
