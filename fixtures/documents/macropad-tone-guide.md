# MacroPad tone keypad

## Upstream example

The source below associates the twelve logical keys with 196, 220, 246, 262,
294, 330, 349, 392, 440, 494, 523, and 587 Hz. Pressing a key lights that pixel
using `colorwheel(int(255 / 12) * key_number)` and starts its tone. Releasing
any key clears every pixel and stops audio, even if another key is still held.

## Scope and limitations

This is a monophonic teaching example, not a polyphonic instrument. It does not
send MIDI or USB keyboard events. Library support for HID and MIDI is distinct
from their use by this application. No tuning accuracy, acoustic level, or
latency bound has been established by the fixture.

## Source: examples/macropad_tone_keypad.py

Unmodified upstream file from [adafruit/Adafruit_CircuitPython_MacroPad@c3b6a690fa71](https://github.com/adafruit/Adafruit_CircuitPython_MacroPad/blob/c3b6a690fa71af3bd39cfd157ea812e6e5d950ea/examples/macropad_tone_keypad.py).
License: Unlicense. SHA-256: `06a5a543e50c93671617c07fb0cdeffa315dbafe9f0d7b22d0ccb36f49a11919`.

````text
# SPDX-FileCopyrightText: 2021 Kattni Rembor for Adafruit Industries
#
# SPDX-License-Identifier: Unlicense
"""
MacroPad tone demo. Plays a different tone for each key pressed and lights up each key a different
color while the key is pressed.
"""

from rainbowio import colorwheel

from adafruit_macropad import MacroPad

macropad = MacroPad()

tones = [196, 220, 246, 262, 294, 330, 349, 392, 440, 494, 523, 587]

while True:
    key_event = macropad.keys.events.get()

    if key_event:
        if key_event.pressed:
            macropad.pixels[key_event.key_number] = colorwheel(int(255 / 12) * key_event.key_number)
            macropad.start_tone(tones[key_event.key_number])

        else:
            macropad.pixels.fill((0, 0, 0))
            macropad.stop_tone()
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
