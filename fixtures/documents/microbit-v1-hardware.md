# micro:bit v1.3 integration notes

## Scope and provenance

This is a selected firmware-facing hardware model for the v1.3 sensor population,
not a complete schematic or semiconductor reference manual. The pinned Zephyr
board definition below includes alternate v1.5 nodes; those disabled nodes are
not populated parts in this fixture. The assembly vendor is recorded as
`microbit`; the notes are authored by Caiman, not the board manufacturer.

## Processor and input wiring

The board definition includes nRF51822 QFAA. Button A is active-low P0.17;
button B is active-low P0.26. The 5 by 5 display is multiplexed using three row
and nine column signals: its wiring is not the v2 wiring.

## Sensors and external sound

The v1.3 accelerometer node is MMA8653FC at I2C address 0x1d. The board file also
mentions MAG3110; this selected model does not model its driver or registers.
The sound application's external piezo uses edge connector P0, mapped here to
MCU P0.03. A ring labeled P0 is not MCU pin P0.00. The piezo is an external test
accessory with no asserted manufacturer or part number. See the sound guide
for its overlay; the bare v1 board has no integrated speaker.

## Modeling limits

LED matrix and button identifiers denote assemblies, not invented IC part
numbers. No sensor register map, timing tolerance, package refdes, or unverified
silicon revision is supplied. See the exact source nodes below for each pin.

## Source: boards/bbc/microbit/doc/index.rst

Unmodified upstream file from [zephyrproject-rtos/zephyr@413b789deb39](https://github.com/zephyrproject-rtos/zephyr/blob/413b789deb391d3a37d06b463288a5fe765ee57e/boards/bbc/microbit/doc/index.rst).
License: Apache-2.0. SHA-256: `72eca157417a6ee84dd168d5ebcb710147d760ba41709da02419e6013a570b88`.

````text
.. zephyr:board:: bbc_microbit

Overview
********

The Micro Bit (also referred to as BBC Micro Bit, stylized as micro:bit) is an
ARM-based embedded system designed by the BBC for use in computer education in
the UK.

The board is 4 cm × 5 cm and has an ARM Cortex-M0 processor, accelerometer and
magnetometer sensors, Bluetooth and USB connectivity, a display consisting of
25 LEDs, two programmable buttons, and can be powered by either USB or an
external battery pack. The device inputs and outputs are through five ring
connectors that are part of the 23-pin edge connector.

More information about the board can be found at the `microbit website`_.

Hardware
********

The micro:bit has the following physical features:

* 25 individually-programmable LEDs
* 2 programmable buttons
* Physical connection pins
* Light and temperature sensors
* Motion sensors (accelerometer and compass)
* Wireless Communication, via Radio and Bluetooth
* USB interface


Supported Features
==================

.. zephyr:board-supported-hw::

Programming and Debugging
*************************

.. zephyr:board-supported-runners::

Flashing
========

Build and flash applications as usual (see :ref:`build_an_application` and
:ref:`application_run` for more details).

Here is an example for the :zephyr:code-sample:`hello_world` application.

First, run your favorite terminal program to listen for output.

.. code-block:: console

   $ minicom -D <tty_device> -b 115200

Replace :code:`<tty_device>` with the port where the board nRF51 DK
can be found. For example, under Linux, :code:`/dev/ttyACM0`.

Then build and flash the application in the usual way.

.. zephyr-app-commands::
   :zephyr-app: samples/hello_world
   :board: bbc_microbit
   :goals: build flash


References
**********

.. target-notes::

.. _microbit website: http://www.microbit.org/
````

## Source: boards/bbc/microbit/bbc_microbit.dts

Unmodified upstream file from [zephyrproject-rtos/zephyr@413b789deb39](https://github.com/zephyrproject-rtos/zephyr/blob/413b789deb391d3a37d06b463288a5fe765ee57e/boards/bbc/microbit/bbc_microbit.dts).
License: Apache-2.0. SHA-256: `9f7e5128509e711060f1678cc032d6d073871cfbf8ea7a5471ccd3b32aeaf81a`.

````text
/*
 * Copyright (c) 2017 Linaro Limited
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/dts-v1/;
#include <nordic/nrf51822_qfaa.dtsi>
#include "bbc_microbit-pinctrl.dtsi"
#include <zephyr/dt-bindings/input/input-event-codes.h>

/ {
	model = "BBC Micro:bit";
	compatible = "bbc,microbit";

	/* These aliases are provided for compatibility with samples */
	aliases {
		sw0 = &buttonA;
		sw1 = &buttonB;
		magn0 = &lsm303agr_magn;
		accel0 = &mma8653fc;
		watchdog0 = &wdt0;
	};

	chosen {
		zephyr,console = &uart0;
		zephyr,shell-uart = &uart0;
		zephyr,bt-mon-uart = &uart0;
		zephyr,bt-c2h-uart = &uart0;
		zephyr,sram = &sram0;
		zephyr,flash = &flash0;
		zephyr,code-partition = &slot0_partition;
		zephyr,display = &led_matrix;
	};

	gpio_keys {
		compatible = "gpio-keys";
		buttonA: button_0 {
			label = "BTN_A";
			gpios = <&gpio0 17 GPIO_ACTIVE_LOW>;
			zephyr,code = <INPUT_KEY_A>;
		};

		buttonB: button_1 {
			label = "BTN_B";
			gpios = <&gpio0 26 GPIO_ACTIVE_LOW>;
			zephyr,code = <INPUT_KEY_B>;
		};
	};

	led_matrix: led_matrix {
		compatible = "nordic,nrf-led-matrix";
		status = "okay";
		width = <5>;
		height = <5>;
		pixel-mapping = [00 13 01 14 02
				 23 24 25 26 27
				 11 08 12 28 10
				 07 06 05 04 03
				 22 16 20 15 21];
		row-gpios = <&gpio0 13 GPIO_ACTIVE_HIGH>,
			    <&gpio0 14 GPIO_ACTIVE_HIGH>,
			    <&gpio0 15 GPIO_ACTIVE_HIGH>;
		col-gpios = <&gpio0  4 GPIO_ACTIVE_LOW>,
			    <&gpio0  5 GPIO_ACTIVE_LOW>,
			    <&gpio0  6 GPIO_ACTIVE_LOW>,
			    <&gpio0  7 GPIO_ACTIVE_LOW>,
			    <&gpio0  8 GPIO_ACTIVE_LOW>,
			    <&gpio0  9 GPIO_ACTIVE_LOW>,
			    <&gpio0 10 GPIO_ACTIVE_LOW>,
			    <&gpio0 11 GPIO_ACTIVE_LOW>,
			    <&gpio0 12 GPIO_ACTIVE_LOW>;
		refresh-frequency = <50>;
		timer = <&timer2>;
		pixel-group-size = <3>;
	};

	edge_connector: connector {
		compatible = "microbit,edge-connector";
		#gpio-cells = <2>;
		gpio-map-mask = <0xffffffff 0xffffffc0>;
		gpio-map-pass-thru = <0 0x3f>;
		gpio-map = <0 0 &gpio0 3 0>,	/* P0, Analog in */
			   <1 0 &gpio0 2 0>,	/* P1, Analog in */
			   <2 0 &gpio0 1 0>,	/* P2, Analog in */
			   <3 0 &gpio0 4 0>,	/* P3, Analog in, LED Col 1 */
			   <4 0 &gpio0 5 0>,	/* P4, Analog in, LED Col 2 */
			   <5 0 &gpio0 17 0>,	/* P5, Button A */
			   <6 0 &gpio0 12 0>,	/* P6, LED Col 9 */
			   <7 0 &gpio0 11 0>,	/* P7, LED Col 8 */
			   <8 0 &gpio0 18 0>,	/* P8 */
			   <9 0 &gpio0 10 0>,	/* P9, LED Col 7 */
			   <10 0 &gpio0 6 0>,	/* P10, Analog in, LED Col 3 */
			   <11 0 &gpio0 26 0>,	/* P11, Button B */
			   <12 0 &gpio0 20 0>,	/* P12 */
			   <13 0 &gpio0 23 0>,	/* P13, SPI1 SCK */
			   <14 0 &gpio0 22 0>,	/* P14, SPI1 MISO */
			   <15 0 &gpio0 21 0>,	/* P15, SPI1 MOSI */
			   <16 0 &gpio0 16 0>,	/* P16 */
			   /* 17 and 18 are just 3.3V pins */
			   <19 0 &gpio0 0 0>,	/* P19, I2C1 SCL */
			   <20 0 &gpio0 30 0>;	/* P20, I2C1 SDA */
	};
};

&gpiote {
	status = "okay";
};

&gpio0 {
	status = "okay";
	/*
	 * Use the sensing mechanism for all pins by default, as GPIOTE channels
	 * are needed for the LED matrix and the SW PWM.
	 */
	sense-edge-mask = <0xffffffff>;
};

&uart0 {
	status = "okay";
	current-speed = <115200>;
	pinctrl-0 = <&uart0_default>;
	pinctrl-1 = <&uart0_sleep>;
	pinctrl-names = "default", "sleep";
};

&i2c0 {
	status = "okay";
	clock-frequency = <I2C_BITRATE_FAST>;

	/* See https://tech.microbit.org/hardware/i2c/ for board variants */

	/* v1.3 MMA8653FC (= FXOS8700) + MAG3110 */
	pinctrl-0 = <&i2c0_default>;
	pinctrl-1 = <&i2c0_sleep>;
	pinctrl-names = "default", "sleep";
	mma8653fc: mma8653fc@1d {
		compatible = "nxp,fxos8700", "nxp,mma8653fc";
		status = "okay";
		reg = <0x1d>;
		int1-gpios = <&gpio0 28 GPIO_ACTIVE_LOW>;
		int2-gpios = <&gpio0 27 GPIO_ACTIVE_LOW>;
	};

	/* v1.5 variant 1 LSM303AGR */
	lsm303agr_magn: lsm303agr-magn@1e {
		compatible = "st,lis2mdl", "st,lsm303agr-magn";
		status = "disabled";
		reg = <0x1e>;
		irq-gpios = <&gpio0 27 GPIO_ACTIVE_HIGH>;	/* A3 */
	};

	lsm303agr_accel: lsm303agr-accel@19 {
		compatible = "st,lis2dh", "st,lsm303agr-accel";
		status = "disabled";
		reg = <0x19>;
		irq-gpios = <&gpio0 28 GPIO_ACTIVE_HIGH>;
	};
};

&flash0 {

	partitions {
		compatible = "fixed-partitions";
		#address-cells = <1>;
		#size-cells = <1>;

		boot_partition: partition@0 {
			label = "mcuboot";
			reg = <0x00000000 0x8000>;
		};
		slot0_partition: partition@8000 {
			label = "image-0";
			reg = <0x00008000 0x1a000>;
		};
		slot1_partition: partition@22000 {
			label = "image-1";
			reg = <0x00022000 0x1a000>;
		};
		scratch_partition: partition@3c000 {
			label = "image-scratch";
			reg = <0x0003c000 0x2000>;
		};
		storage_partition: partition@3e000 {
			label = "storage";
			reg = <0x0003e000 0x00002000>;
		};
	};
};
````

## License notices

Caiman adds the introductory notes and Markdown wrappers; upstream files above are unchanged.

### Apache-2.0

````text
                                 Apache License
                           Version 2.0, January 2004
                        http://www.apache.org/licenses/

   TERMS AND CONDITIONS FOR USE, REPRODUCTION, AND DISTRIBUTION

   1. Definitions.

      "License" shall mean the terms and conditions for use, reproduction,
      and distribution as defined by Sections 1 through 9 of this document.

      "Licensor" shall mean the copyright owner or entity authorized by
      the copyright owner that is granting the License.

      "Legal Entity" shall mean the union of the acting entity and all
      other entities that control, are controlled by, or are under common
      control with that entity. For the purposes of this definition,
      "control" means (i) the power, direct or indirect, to cause the
      direction or management of such entity, whether by contract or
      otherwise, or (ii) ownership of fifty percent (50%) or more of the
      outstanding shares, or (iii) beneficial ownership of such entity.

      "You" (or "Your") shall mean an individual or Legal Entity
      exercising permissions granted by this License.

      "Source" form shall mean the preferred form for making modifications,
      including but not limited to software source code, documentation
      source, and configuration files.

      "Object" form shall mean any form resulting from mechanical
      transformation or translation of a Source form, including but
      not limited to compiled object code, generated documentation,
      and conversions to other media types.

      "Work" shall mean the work of authorship, whether in Source or
      Object form, made available under the License, as indicated by a
      copyright notice that is included in or attached to the work
      (an example is provided in the Appendix below).

      "Derivative Works" shall mean any work, whether in Source or Object
      form, that is based on (or derived from) the Work and for which the
      editorial revisions, annotations, elaborations, or other modifications
      represent, as a whole, an original work of authorship. For the purposes
      of this License, Derivative Works shall not include works that remain
      separable from, or merely link (or bind by name) to the interfaces of,
      the Work and Derivative Works thereof.

      "Contribution" shall mean any work of authorship, including
      the original version of the Work and any modifications or additions
      to that Work or Derivative Works thereof, that is intentionally
      submitted to Licensor for inclusion in the Work by the copyright owner
      or by an individual or Legal Entity authorized to submit on behalf of
      the copyright owner. For the purposes of this definition, "submitted"
      means any form of electronic, verbal, or written communication sent
      to the Licensor or its representatives, including but not limited to
      communication on electronic mailing lists, source code control systems,
      and issue tracking systems that are managed by, or on behalf of, the
      Licensor for the purpose of discussing and improving the Work, but
      excluding communication that is conspicuously marked or otherwise
      designated in writing by the copyright owner as "Not a Contribution."

      "Contributor" shall mean Licensor and any individual or Legal Entity
      on behalf of whom a Contribution has been received by Licensor and
      subsequently incorporated within the Work.

   2. Grant of Copyright License. Subject to the terms and conditions of
      this License, each Contributor hereby grants to You a perpetual,
      worldwide, non-exclusive, no-charge, royalty-free, irrevocable
      copyright license to reproduce, prepare Derivative Works of,
      publicly display, publicly perform, sublicense, and distribute the
      Work and such Derivative Works in Source or Object form.

   3. Grant of Patent License. Subject to the terms and conditions of
      this License, each Contributor hereby grants to You a perpetual,
      worldwide, non-exclusive, no-charge, royalty-free, irrevocable
      (except as stated in this section) patent license to make, have made,
      use, offer to sell, sell, import, and otherwise transfer the Work,
      where such license applies only to those patent claims licensable
      by such Contributor that are necessarily infringed by their
      Contribution(s) alone or by combination of their Contribution(s)
      with the Work to which such Contribution(s) was submitted. If You
      institute patent litigation against any entity (including a
      cross-claim or counterclaim in a lawsuit) alleging that the Work
      or a Contribution incorporated within the Work constitutes direct
      or contributory patent infringement, then any patent licenses
      granted to You under this License for that Work shall terminate
      as of the date such litigation is filed.

   4. Redistribution. You may reproduce and distribute copies of the
      Work or Derivative Works thereof in any medium, with or without
      modifications, and in Source or Object form, provided that You
      meet the following conditions:

      (a) You must give any other recipients of the Work or
          Derivative Works a copy of this License; and

      (b) You must cause any modified files to carry prominent notices
          stating that You changed the files; and

      (c) You must retain, in the Source form of any Derivative Works
          that You distribute, all copyright, patent, trademark, and
          attribution notices from the Source form of the Work,
          excluding those notices that do not pertain to any part of
          the Derivative Works; and

      (d) If the Work includes a "NOTICE" text file as part of its
          distribution, then any Derivative Works that You distribute must
          include a readable copy of the attribution notices contained
          within such NOTICE file, excluding those notices that do not
          pertain to any part of the Derivative Works, in at least one
          of the following places: within a NOTICE text file distributed
          as part of the Derivative Works; within the Source form or
          documentation, if provided along with the Derivative Works; or,
          within a display generated by the Derivative Works, if and
          wherever such third-party notices normally appear. The contents
          of the NOTICE file are for informational purposes only and
          do not modify the License. You may add Your own attribution
          notices within Derivative Works that You distribute, alongside
          or as an addendum to the NOTICE text from the Work, provided
          that such additional attribution notices cannot be construed
          as modifying the License.

      You may add Your own copyright statement to Your modifications and
      may provide additional or different license terms and conditions
      for use, reproduction, or distribution of Your modifications, or
      for any such Derivative Works as a whole, provided Your use,
      reproduction, and distribution of the Work otherwise complies with
      the conditions stated in this License.

   5. Submission of Contributions. Unless You explicitly state otherwise,
      any Contribution intentionally submitted for inclusion in the Work
      by You to the Licensor shall be under the terms and conditions of
      this License, without any additional terms or conditions.
      Notwithstanding the above, nothing herein shall supersede or modify
      the terms of any separate license agreement you may have executed
      with Licensor regarding such Contributions.

   6. Trademarks. This License does not grant permission to use the trade
      names, trademarks, service marks, or product names of the Licensor,
      except as required for reasonable and customary use in describing the
      origin of the Work and reproducing the content of the NOTICE file.

   7. Disclaimer of Warranty. Unless required by applicable law or
      agreed to in writing, Licensor provides the Work (and each
      Contributor provides its Contributions) on an "AS IS" BASIS,
      WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
      implied, including, without limitation, any warranties or conditions
      of TITLE, NON-INFRINGEMENT, MERCHANTABILITY, or FITNESS FOR A
      PARTICULAR PURPOSE. You are solely responsible for determining the
      appropriateness of using or redistributing the Work and assume any
      risks associated with Your exercise of permissions under this License.

   8. Limitation of Liability. In no event and under no legal theory,
      whether in tort (including negligence), contract, or otherwise,
      unless required by applicable law (such as deliberate and grossly
      negligent acts) or agreed to in writing, shall any Contributor be
      liable to You for damages, including any direct, indirect, special,
      incidental, or consequential damages of any character arising as a
      result of this License or out of the use or inability to use the
      Work (including but not limited to damages for loss of goodwill,
      work stoppage, computer failure or malfunction, or any and all
      other commercial damages or losses), even if such Contributor
      has been advised of the possibility of such damages.

   9. Accepting Warranty or Additional Liability. While redistributing
      the Work or Derivative Works thereof, You may choose to offer,
      and charge a fee for, acceptance of support, warranty, indemnity,
      or other liability obligations and/or rights consistent with this
      License. However, in accepting such obligations, You may act only
      on Your own behalf and on Your sole responsibility, not on behalf
      of any other Contributor, and only if You agree to indemnify,
      defend, and hold each Contributor harmless for any liability
      incurred by, or claims asserted against, such Contributor by reason
      of your accepting any such warranty or additional liability.

   END OF TERMS AND CONDITIONS

   APPENDIX: How to apply the Apache License to your work.

      To apply the Apache License to your work, attach the following
      boilerplate notice, with the fields enclosed by brackets "{}"
      replaced with your own identifying information. (Don't include
      the brackets!)  The text should be enclosed in the appropriate
      comment syntax for the file format. We also recommend that a
      file or class name and description of purpose be included on the
      same "printed page" as the copyright notice for easier
      identification within third-party archives.

   Copyright {yyyy} {name of copyright owner}

   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.

````
