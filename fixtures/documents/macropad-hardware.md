# MacroPad RP2040 integration notes

## Scope and provenance

This is a selected board model based on CircuitPython 9.2.8's MacroPad definition,
not a numbered PCB revision or a full BOM. The notes are Caiman-authored; the
MIT-licensed board sources and their copyright notices follow below.

## Controller and storage

The target selects RP2040 and external flash family `W25Q64JVxQ`. That family
identifier is retained without inventing a package suffix or a board refdes.

## Key and encoder wiring

KEY1 through KEY12 map to GPIO1 through GPIO12. CircuitPython key-event indices
are zero-based, so event 0 refers to KEY1. The encoder A/B signals are GPIO17
and GPIO18, and its switch is GPIO0. The helper library pulls the switch up and
provides a debounced interface for the HID example.

## Display and lighting

The firmware initializes a 128 by 64 monochrome display with SH1107 addressing.
Its SPI clock is GPIO26 and MOSI is GPIO27, with CS GPIO22, reset GPIO23, and
D/C GPIO24. `board_init` sets 10 MHz, polarity 0, phase 0. The model calls this
an OLED assembly rather than asserting an unverified controller part number.
There are twelve NeoPixels on GPIO19, plus a separate status LED on GPIO13.

## Audio and expansion

Speaker PWM is GPIO16 with enable GPIO14. The I2C expansion bus uses SDA GPIO20
and SCL GPIO21; no external I2C device is assumed connected. The HID and tone
projects share this board but select different features.

## Source: ports/raspberrypi/boards/adafruit_macropad_rp2040/board.c

Unmodified upstream file from [adafruit/circuitpython@361dbc02066f](https://github.com/adafruit/circuitpython/blob/361dbc02066f8d2b83c3a7f1f4993a9a590d1239/ports/raspberrypi/boards/adafruit_macropad_rp2040/board.c).
License: MIT. SHA-256: `2c1f98c3ee32f2d4309efa0b24ce0acf64db6f5d72073a3692f126778e2778a7`.

````text
// This file is part of the CircuitPython project: https://circuitpython.org
//
// SPDX-FileCopyrightText: Copyright (c) 2021 Scott Shawcroft for Adafruit Industries
//
// SPDX-License-Identifier: MIT

#include "shared-bindings/board/__init__.h"
#include "shared-bindings/fourwire/FourWire.h"
#include "shared-module/displayio/__init__.h"
#include "shared-module/displayio/mipi_constants.h"
#include "shared-bindings/busio/SPI.h"
#include "shared-bindings/microcontroller/Pin.h"
#include "hardware/gpio.h"
#include "supervisor/board.h"
#include "supervisor/shared/board.h"


#define DELAY 0x80

uint8_t display_init_sequence[] = {
    0xae, 0, // sleep
    0xd5, 1, 0x80, // fOsc divide by 2
    0xa8, 1, 0x3f, // multiplex 64
    0xd3, 1, 0x00, // offset 0
    0x40, 1, 0x00, // start line 0
    0xad, 1, 0x8b, // dc/dc on
    0xa1, 0, // segment remap = 0
    0xc8, 0, // scan incr
    0xda, 1, 0x12, // com pins
    0x81, 1, 0xff, // contrast 255
    0xd9, 1, 0x1f, // pre/dis-charge 2DCLKs/2CLKs
    0xdb, 1, 0x20, // VCOM deslect 0.770
    0x20, 1, 0x20,
    0x33, 0, // VPP 9V
    0xa6, 0, // not inverted
    0xa4, 0, // normal
    0xaf, 0, // on
};

void board_init(void) {
    fourwire_fourwire_obj_t *bus = &allocate_display_bus()->fourwire_bus;
    busio_spi_obj_t *spi = &bus->inline_bus;
    common_hal_busio_spi_construct(spi, &pin_GPIO26, &pin_GPIO27, NULL, false);
    common_hal_busio_spi_never_reset(spi);

    bus->base.type = &fourwire_fourwire_type;
    common_hal_fourwire_fourwire_construct(bus,
        spi,
        &pin_GPIO24, // Command or data
        &pin_GPIO22, // Chip select
        &pin_GPIO23, // Reset
        10000000, // Baudrate
        0, // Polarity
        0); // Phase

    busdisplay_busdisplay_obj_t *display = &allocate_display()->display;
    display->base.type = &busdisplay_busdisplay_type;
    common_hal_busdisplay_busdisplay_construct(display,
        bus,
        128, // Width
        64, // Height
        2, // column start
        0, // row start
        0, // rotation
        1, // Color depth
        true, // grayscale
        false, // pixels in byte share row. Only used with depth < 8
        1, // bytes per cell. Only valid for depths < 8
        false, // reverse_pixels_in_byte. Only valid for depths < 8
        true, // reverse_pixels_in_word
        0, // Set column command
        0, // Set row command
        0, // Write memory command
        display_init_sequence,
        sizeof(display_init_sequence),
        NULL,
        0x81,
        1.0f, // brightness
        true, // single_byte_bounds
        true, // data as commands
        true, // auto_refresh
        60, // native_frames_per_second
        true, // backlight_on_high
        true, // SH1107_addressing
        50000); // backlight pwm frequency
}

void reset_board(void) {
    // turn off any left over LED
    board_reset_user_neopixels(&pin_GPIO19, 12);
}

// Use the MP_WEAK supervisor/shared/board.c versions of routines not defined here.
````

## Source: ports/raspberrypi/boards/adafruit_macropad_rp2040/pins.c

Unmodified upstream file from [adafruit/circuitpython@361dbc02066f](https://github.com/adafruit/circuitpython/blob/361dbc02066f8d2b83c3a7f1f4993a9a590d1239/ports/raspberrypi/boards/adafruit_macropad_rp2040/pins.c).
License: MIT. SHA-256: `6a3f1bbbe84d8468ea72b0dd43f62db0bb6e41a4502011808cbf3ee1f7ffd6c6`.

````text
// This file is part of the CircuitPython project: https://circuitpython.org
//
// SPDX-FileCopyrightText: Copyright (c) 2021 Scott Shawcroft for Adafruit Industries
//
// SPDX-License-Identifier: MIT

#include "shared-bindings/board/__init__.h"
#include "shared-module/displayio/__init__.h"

static const mp_rom_map_elem_t board_module_globals_table[] = {
    CIRCUITPYTHON_BOARD_DICT_STANDARD_ITEMS

    { MP_ROM_QSTR(MP_QSTR_KEY1), MP_ROM_PTR(&pin_GPIO1) },
    { MP_ROM_QSTR(MP_QSTR_KEY2), MP_ROM_PTR(&pin_GPIO2) },
    { MP_ROM_QSTR(MP_QSTR_KEY3), MP_ROM_PTR(&pin_GPIO3) },
    { MP_ROM_QSTR(MP_QSTR_KEY4), MP_ROM_PTR(&pin_GPIO4) },
    { MP_ROM_QSTR(MP_QSTR_KEY5), MP_ROM_PTR(&pin_GPIO5) },
    { MP_ROM_QSTR(MP_QSTR_KEY6), MP_ROM_PTR(&pin_GPIO6) },
    { MP_ROM_QSTR(MP_QSTR_KEY7), MP_ROM_PTR(&pin_GPIO7) },
    { MP_ROM_QSTR(MP_QSTR_KEY8), MP_ROM_PTR(&pin_GPIO8) },
    { MP_ROM_QSTR(MP_QSTR_KEY9), MP_ROM_PTR(&pin_GPIO9) },
    { MP_ROM_QSTR(MP_QSTR_KEY10), MP_ROM_PTR(&pin_GPIO10) },
    { MP_ROM_QSTR(MP_QSTR_KEY11), MP_ROM_PTR(&pin_GPIO11) },
    { MP_ROM_QSTR(MP_QSTR_KEY12), MP_ROM_PTR(&pin_GPIO12) },

    { MP_ROM_QSTR(MP_QSTR_LED), MP_ROM_PTR(&pin_GPIO13) },

    { MP_ROM_QSTR(MP_QSTR_SPEAKER_ENABLE), MP_ROM_PTR(&pin_GPIO14) },
    { MP_ROM_QSTR(MP_QSTR_SPEAKER), MP_ROM_PTR(&pin_GPIO16) },

    { MP_ROM_QSTR(MP_QSTR_ENCODER_SWITCH), MP_ROM_PTR(&pin_GPIO0) },
    { MP_ROM_QSTR(MP_QSTR_BUTTON), MP_ROM_PTR(&pin_GPIO0) },

    { MP_ROM_QSTR(MP_QSTR_ENCODER_A), MP_ROM_PTR(&pin_GPIO17) },
    { MP_ROM_QSTR(MP_QSTR_ROTA), MP_ROM_PTR(&pin_GPIO17) },
    { MP_ROM_QSTR(MP_QSTR_ENCODER_B), MP_ROM_PTR(&pin_GPIO18) },
    { MP_ROM_QSTR(MP_QSTR_ROTB), MP_ROM_PTR(&pin_GPIO18) },

    { MP_ROM_QSTR(MP_QSTR_NEOPIXEL), MP_ROM_PTR(&pin_GPIO19) },

    { MP_ROM_QSTR(MP_QSTR_SDA), MP_ROM_PTR(&pin_GPIO20) },
    { MP_ROM_QSTR(MP_QSTR_SCL), MP_ROM_PTR(&pin_GPIO21) },

    { MP_ROM_QSTR(MP_QSTR_OLED_CS), MP_ROM_PTR(&pin_GPIO22) },
    { MP_ROM_QSTR(MP_QSTR_OLED_RESET), MP_ROM_PTR(&pin_GPIO23) },
    { MP_ROM_QSTR(MP_QSTR_OLED_DC), MP_ROM_PTR(&pin_GPIO24) },


    { MP_ROM_QSTR(MP_QSTR_SCK), MP_ROM_PTR(&pin_GPIO26) },
    { MP_ROM_QSTR(MP_QSTR_MOSI), MP_ROM_PTR(&pin_GPIO27) },
    { MP_ROM_QSTR(MP_QSTR_MISO), MP_ROM_PTR(&pin_GPIO28) },

    { MP_ROM_QSTR(MP_QSTR_I2C), MP_ROM_PTR(&board_i2c_obj) },
    { MP_ROM_QSTR(MP_QSTR_STEMMA_I2C), MP_ROM_PTR(&board_i2c_obj) },
    { MP_ROM_QSTR(MP_QSTR_SPI), MP_ROM_PTR(&board_spi_obj) },

    { MP_ROM_QSTR(MP_QSTR_DISPLAY), MP_ROM_PTR(&displays[0].display)}
};
MP_DEFINE_CONST_DICT(board_module_globals, board_module_globals_table);
````

## Source: ports/raspberrypi/boards/adafruit_macropad_rp2040/mpconfigboard.h

Unmodified upstream file from [adafruit/circuitpython@361dbc02066f](https://github.com/adafruit/circuitpython/blob/361dbc02066f8d2b83c3a7f1f4993a9a590d1239/ports/raspberrypi/boards/adafruit_macropad_rp2040/mpconfigboard.h).
License: MIT. SHA-256: `1c004e2c812b99603e97b170a5790b1c786e4bf2bb58856f1f5adceddcecbf07`.

````text
// This file is part of the CircuitPython project: https://circuitpython.org
//
// SPDX-FileCopyrightText: Copyright (c) 2021 Scott Shawcroft for Adafruit Industries
//
// SPDX-License-Identifier: MIT

#pragma once

#define MICROPY_HW_BOARD_NAME "Adafruit Macropad RP2040"
#define MICROPY_HW_MCU_NAME "rp2040"

#define MICROPY_HW_NEOPIXEL (&pin_GPIO19)

#define DEFAULT_I2C_BUS_SCL (&pin_GPIO21)
#define DEFAULT_I2C_BUS_SDA (&pin_GPIO20)

#define DEFAULT_SPI_BUS_SCK (&pin_GPIO26)
#define DEFAULT_SPI_BUS_MOSI (&pin_GPIO27)
#define DEFAULT_SPI_BUS_MISO (&pin_GPIO28)
````

## Source: ports/raspberrypi/boards/adafruit_macropad_rp2040/mpconfigboard.mk

Unmodified upstream file from [adafruit/circuitpython@361dbc02066f](https://github.com/adafruit/circuitpython/blob/361dbc02066f8d2b83c3a7f1f4993a9a590d1239/ports/raspberrypi/boards/adafruit_macropad_rp2040/mpconfigboard.mk).
License: MIT. SHA-256: `813e54b5aad67a909a6754987daa1db8c485b30922814c70ceed3fd3ae16493f`.

````text
USB_VID = 0x239A
USB_PID = 0x8108
USB_PRODUCT = "Macropad RP2040"
USB_MANUFACTURER = "Adafruit"

CHIP_VARIANT = RP2040
CHIP_FAMILY = rp2

EXTERNAL_FLASH_DEVICES = "W25Q64JVxQ"
````

## License notices

Caiman adds the introductory notes and Markdown wrappers; upstream files above are unchanged.

### MIT-CircuitPython

````text
The MIT License (MIT)

Copyright (c) 2013-2023 Damien P. George

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.

--------------------------------------------------------------------------------

# CIRCUITPY-CHANGE:

Unless specified otherwise (see below), the above license and copyright applies
to all files derived from MicroPython in this repository.

Individual files may include additional copyright holders and specify other licenses.
See the comments and SPDX headers.
````
