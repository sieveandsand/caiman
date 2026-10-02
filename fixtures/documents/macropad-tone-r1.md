# MacroPad tone acceptance baseline R1

These are Caiman-authored example acceptance criteria derived from the linked
upstream application. They are not an upstream specification, a customer
contract, or evidence of hardware validation. Requirement IDs and release names
are local to this dataset. This document is public; the project compartment is
only an example grouping. Acceptance checks below are proposed, not executed.

## Key-to-tone mapping

REQ-TONE-001: At default rotation, keys 0 through 11 shall select the frequency
array in the pinned tone example: 196, 220, 246, 262, 294, 330, 349, 392, 440,
494, 523, and 587 Hz. A press shall start that tone and color the selected pixel
using the example's colorwheel expression. Source: `tones` and the pressed branch.

## Release behavior

REQ-TONE-002: Releasing any key shall stop the tone and clear all twelve pixels.
The application is monophonic. Include an overlapping two-key test to expose
this behavior; do not replace it with an assumed per-key release policy.
Source: `macropad_tone_keypad.py`, the release branch.

## Application scope

REQ-TONE-003: Speaker output and per-key lighting shall be required. USB HID,
MIDI, encoder navigation, and an OLED status UI shall not be required by this
example. Source: the complete tone example; the hardware and library still
expose those capabilities to other applications on this board.
