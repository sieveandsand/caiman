# MacroPad HID acceptance baseline R1

These are Caiman-authored example acceptance criteria derived from the linked
upstream application. They are not an upstream specification, a customer
contract, or evidence of hardware validation. Requirement IDs and release names
are local to this dataset. This document is public; the project compartment is
only an example grouping. Acceptance checks below are proposed, not executed.

## Key bindings

REQ-HID-001: At default rotation, logical keys 0 through 3 shall produce A,
Shift+B followed by release, the source greeting, and volume decrement,
respectively. Use a US-layout host to evaluate text output. Key release shall
not repeat the key-press action. Source: `macropad_keyboard_mouse.py`, key-event loop.

## Pointer input

REQ-HID-002: A debounced encoder-switch press shall send one right-click action.
Each loop-observed increase or decrease in encoder position shall move the pointer
by +5 or -5 horizontal units. Do not assert five units per physical detent if the
loop missed intermediate positions. Source: the example's encoder block.

## Application scope

REQ-HID-003: This example shall use USB HID keyboard, consumer control, and mouse.
Audio, MIDI, and an OLED status UI are outside its required application scope.
Acceptance shall run in an expendable focused host window. Source: the complete
example and the helper library's HID properties. No Caiman import runs this code.
