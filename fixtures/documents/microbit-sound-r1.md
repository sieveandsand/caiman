# micro:bit sound acceptance baseline R1

These are Caiman-authored example acceptance criteria derived from the linked
upstream application. They are not an upstream specification, a customer
contract, or evidence of hardware validation. Requirement IDs and release names
are local to this dataset. This document is public; the project compartment is
only an example grouping. Acceptance checks below are proposed, not executed.

## Hardware scope

REQ-SOUND-001: The R1 configuration shall target the micro:bit v1.3 model and an
external piezo connected through edge P0. Check the selected board and overlay;
reject the v2 PWM1 route for this release.

## Frequency control

REQ-SOUND-002: Initial period shall be 1500 us. Accepted A presses shall add
50 us up to 3900 us; accepted B presses shall subtract 50 us down to 50 us.
Check both limits and repeated presses. The 5 by 5 display shall show integer
frequency in Hz, calculated from the period, after an accepted press.

## Beep lifecycle

REQ-SOUND-003: Button-triggered beeps shall use 50 percent duty for a nominal
60 ms, followed by PWM off and a nominal 50 ms silent busy interval. Presses
while the busy flag is set shall not enqueue another beep. Test accepted presses
separately from startup; the source startup flag behavior is described in the guide.

## Release scope

REQ-SOUND-004: R1 shall require the external sound accessory; operation with only
the bare board is outside its acceptance setup. Sensors and Bluetooth shall not
be application features. A startup beep shall be included, without claiming
interrupt-race protection beyond what the pinned source implements.

## Traceability

Basis: Zephyr v4.2.0, `samples/boards/bbc/microbit/sound/src/main.c`, constants,
`button_pressed`, `beep`, and `main`; both board overlays; the v1 board source.
See the companion source documents for commit-pinned URLs and full license notices.
