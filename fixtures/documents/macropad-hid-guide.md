# MacroPad keyboard and mouse

## Upstream example

The source below is an actual Adafruit example, licensed separately from the
helper library. It maps logical key 0 to A, key 1 to Shift+B followed by release,
key 2 to a greeting through the keyboard layout, and key 3 to volume decrement.
The debounced encoder switch sends a right click. Encoder position changes move
the mouse horizontally by five units per observed direction change. The loop
does not multiply movement by the full encoder delta; rapid rotation may skip
intermediate positions.

## Operating assumptions

This example sends input to the attached USB host and whichever application has
focus. For bench evaluation use an expendable text editor window and observe
volume and pointer changes. Importing these Caiman fixtures does not execute the
example, send USB input, or install code on a board.

## Source: examples/macropad_keyboard_mouse.py

Unmodified upstream file from [adafruit/Adafruit_CircuitPython_MacroPad@c3b6a690fa71](https://github.com/adafruit/Adafruit_CircuitPython_MacroPad/blob/c3b6a690fa71af3bd39cfd157ea812e6e5d950ea/examples/macropad_keyboard_mouse.py).
License: Unlicense. SHA-256: `9ab1da4399a77b8455b014bcfe40383be92d9343406eb95eb40453afe2b199f4`.

````text
# SPDX-FileCopyrightText: 2021 Kattni Rembor for Adafruit Industries
#
# SPDX-License-Identifier: Unlicense
"""
MacroPad HID keyboard and mouse demo. The demo sends "a" when the first key is pressed, a "B" when
the second key is pressed, "Hello, World!" when the third key is pressed, and decreases the volume
when the fourth key is pressed. It sends a right mouse click when the rotary encoder switch is
pressed. Finally, it moves the mouse left and right when the rotary encoder is rotated
counterclockwise and clockwise respectively.
"""

from adafruit_macropad import MacroPad

macropad = MacroPad()

last_position = 0
while True:
    key_event = macropad.keys.events.get()

    if key_event:
        if key_event.pressed:
            if key_event.key_number == 0:
                macropad.keyboard.send(macropad.Keycode.A)
            if key_event.key_number == 1:
                macropad.keyboard.press(macropad.Keycode.SHIFT, macropad.Keycode.B)
                macropad.keyboard.release_all()
            if key_event.key_number == 2:
                macropad.keyboard_layout.write("Hello, World!")
            if key_event.key_number == 3:
                macropad.consumer_control.send(macropad.ConsumerControlCode.VOLUME_DECREMENT)

    macropad.encoder_switch_debounced.update()

    if macropad.encoder_switch_debounced.pressed:
        macropad.mouse.click(macropad.Mouse.RIGHT_BUTTON)

    current_position = macropad.encoder

    if macropad.encoder > last_position:
        macropad.mouse.move(x=+5)
        last_position = current_position

    if macropad.encoder < last_position:
        macropad.mouse.move(x=-5)
        last_position = current_position
````

## License notices

Caiman adds the introductory notes and Markdown wrappers; upstream files above are unchanged.

### Unlicense

````text
This is free and unencumbered software released into the public domain.

Anyone is free to copy, modify, publish, use, compile, sell, or distribute
this software, either in source code form or as a compiled binary, for any
purpose, commercial or non-commercial, and by any means.

In jurisdictions that recognize copyright laws, the author or authors of this
software dedicate any and all copyright interest in the software to the public
domain. We make this dedication for the benefit of the public at large and
to the detriment of our heirs and successors. We intend this dedication to
be an overt act of relinquishment in perpetuity of all present and future
rights to this software under copyright law.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS
FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS
BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH
THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE. For more information,
please refer to <https://unlicense.org/>
````
