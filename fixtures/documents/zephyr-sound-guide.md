# Zephyr micro:bit sound application

## Application behavior

This real Zephyr sample is a two-button tone generator. The definitions and
functions in `src/main.c` below are the authority for this snapshot. The initial
period comes from each board overlay: 1500 microseconds. Button A increases
period by 50 microseconds up to 3900; button B decreases it down to 50. Increasing
period lowers frequency. The display shows integer Hz, not the period.

## Timing and busy behavior

The work item drives 50 percent duty for 60 ms, disables PWM, then waits 50 ms
before clearing its busy flag. A button press while the flag is set is ignored;
it is not queued. Startup submits one beep. These are source-level behaviors,
not measured timing guarantees or a certification result. The startup work item
is submitted without first setting the busy flag; do not claim the initial beep
has identical concurrency protection to button-triggered beeps.

## Build context

Use a separately installed Zephyr v4.2.0 workspace and its dependencies. In that
workspace, build `samples/boards/bbc/microbit/sound` with `west build -b
bbc_microbit` or `west build -b bbc_microbit_v2`. The fixtures do not install a
Zephyr SDK, build firmware, or flash a device. The source README and overlays
below describe the external piezo requirement for v1 and the integrated v2 path.

## Source: samples/boards/bbc/microbit/sound/README.rst

Unmodified upstream file from [zephyrproject-rtos/zephyr@413b789deb39](https://github.com/zephyrproject-rtos/zephyr/blob/413b789deb391d3a37d06b463288a5fe765ee57e/samples/boards/bbc/microbit/sound/README.rst).
License: Apache-2.0. SHA-256: `492a983446a23a5cacd0fb86a4d1c678da73dc7ac7ad44315a512058c55da40d`.

````text
.. zephyr:code-sample:: bbc_microbit_sound
   :name: Sound
   :relevant-api: pwm_interface

   Use the piezo buzzer on the BBC micro:bit board.

Overview
********

This sample demonstrates how to use a piezo buzzer connected
to port P0 on the edge connector of the **BBC micro:bit v1** or
using the on-board buzzer on the **BBC micro:bit v2**.

Requirements
************

Using **BBC micro:bit v1**, a separate piezo buzzer must be connected to the board.
One example is the MI:Power board that has a piezo buzzer in addition to a
coin-cell battery. Resellers of this board can be fairly easily found using online search.

The upgraded **BBC micro:bit v2** board does not need a separate buzzer as it has one
built-in on the backside of the board (marked as 'speaker').


Building and running
********************

The sample can be built as follows:

Building for a BBC micro:bit v1
-------------------------------

.. zephyr-app-commands::
   :zephyr-app: samples/boards/bbc/microbit/sound
   :board: bbc_microbit
   :goals: build flash
   :compact:

Building for a BBC micro:bit v2
-------------------------------

.. zephyr-app-commands::
   :zephyr-app: samples/boards/bbc/microbit/sound
   :board: bbc_microbit_v2
   :goals: build flash
   :compact:

Sample Output
=============

This sample outputs sounds through a piezo buzzer based on
button presses of the two main buttons. For each press the current
output frequency will be printed on the 5x5 LED display.
````

## Source: samples/boards/bbc/microbit/sound/src/main.c

Unmodified upstream file from [zephyrproject-rtos/zephyr@413b789deb39](https://github.com/zephyrproject-rtos/zephyr/blob/413b789deb391d3a37d06b463288a5fe765ee57e/samples/boards/bbc/microbit/sound/src/main.c).
License: Apache-2.0. SHA-256: `4e7351297d12ad6f12bac8098e7d51fa93b0c2ff3794109837347a0b7a52363c`.

````text
/*
 * Copyright (c) 2017 Intel Corporation
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <zephyr/kernel.h>
#include <zephyr/sys/printk.h>
#include <zephyr/drivers/gpio.h>
#include <zephyr/drivers/pwm.h>
#include <zephyr/device.h>

#include <zephyr/display/mb_display.h>

#define PERIOD_MIN     PWM_USEC(50)
#define PERIOD_MAX     PWM_USEC(3900)

#define BEEP_DURATION  K_MSEC(60)

#define NS_TO_HZ(_ns)  (NSEC_PER_SEC / (_ns))

static const struct pwm_dt_spec pwm = PWM_DT_SPEC_GET(DT_PATH(zephyr_user));

static uint32_t period;
static struct k_work beep_work;
static volatile bool beep_active;

static const struct gpio_dt_spec sw0_gpio = GPIO_DT_SPEC_GET(DT_ALIAS(sw0), gpios);
static const struct gpio_dt_spec sw1_gpio = GPIO_DT_SPEC_GET(DT_ALIAS(sw1), gpios);

/* ensure SW0 & SW1 are on same gpio controller */
BUILD_ASSERT(DT_SAME_NODE(DT_GPIO_CTLR(DT_ALIAS(sw0), gpios), DT_GPIO_CTLR(DT_ALIAS(sw1), gpios)));

static void beep(struct k_work *work)
{
	/* The "period / 2" pulse duration gives 50% duty cycle, which
	 * should result in the maximum sound volume.
	 */
	pwm_set_dt(&pwm, period, period / 2U);
	k_sleep(BEEP_DURATION);

	/* Disable the PWM */
	pwm_set_pulse_dt(&pwm, 0);

	/* Ensure there's a clear silent period between two tones */
	k_sleep(K_MSEC(50));
	beep_active = false;
}

static void button_pressed(const struct device *dev, struct gpio_callback *cb,
			   uint32_t pins)
{
	struct mb_display *disp;

	if (beep_active) {
		printk("Button press while beeping\n");
		return;
	}

	beep_active = true;

	if (pins & BIT(sw0_gpio.pin)) {
		printk("A pressed\n");
		if (period < PERIOD_MAX) {
			period += PWM_USEC(50U);
		}
	} else {
		printk("B pressed\n");
		if (period > PERIOD_MIN) {
			period -= PWM_USEC(50U);
		}
	}

	printk("Period is %u us (%u Hz)\n", period / NSEC_PER_USEC,
	       NS_TO_HZ(period));

	disp = mb_display_get();
	mb_display_print(disp, MB_DISPLAY_MODE_DEFAULT, 500, "%uHz",
			 NS_TO_HZ(period));

	k_work_submit(&beep_work);
}

int main(void)
{
	static struct gpio_callback button_cb_data;

	if (!pwm_is_ready_dt(&pwm)) {
		printk("%s: device not ready.\n", pwm.dev->name);
		return 0;
	}

	/* since sw0_gpio.port == sw1_gpio.port, we only need to check ready once */
	if (!gpio_is_ready_dt(&sw0_gpio)) {
		printk("%s: device not ready.\n", sw0_gpio.port->name);
		return 0;
	}

	period = pwm.period;

	gpio_pin_configure_dt(&sw0_gpio, GPIO_INPUT);
	gpio_pin_configure_dt(&sw1_gpio, GPIO_INPUT);

	gpio_pin_interrupt_configure_dt(&sw0_gpio, GPIO_INT_EDGE_TO_ACTIVE);
	gpio_pin_interrupt_configure_dt(&sw1_gpio, GPIO_INT_EDGE_TO_ACTIVE);

	gpio_init_callback(&button_cb_data, button_pressed,
			   BIT(sw0_gpio.pin) | BIT(sw1_gpio.pin));

	k_work_init(&beep_work, beep);
	/* Notify with a beep that we've started */
	k_work_submit(&beep_work);

	gpio_add_callback(sw0_gpio.port, &button_cb_data);
	return 0;
}
````

## Source: samples/boards/bbc/microbit/sound/boards/bbc_microbit.overlay

Unmodified upstream file from [zephyrproject-rtos/zephyr@413b789deb39](https://github.com/zephyrproject-rtos/zephyr/blob/413b789deb391d3a37d06b463288a5fe765ee57e/samples/boards/bbc/microbit/sound/boards/bbc_microbit.overlay).
License: Apache-2.0. SHA-256: `c946e99d558058d374373eb5f3e555af4513969f9d31eb16a752e46366045c60`.

````text
/ {
	zephyr,user {
		/* period cell corresponds to initial period */
		pwms = <&sw_pwm 0 PWM_USEC(1500) PWM_POLARITY_NORMAL>;
	};
};

&sw_pwm {
	status = "okay";
	channel-gpios = <&edge_connector 0 GPIO_ACTIVE_HIGH>;
};
````

## Source: samples/boards/bbc/microbit/sound/boards/bbc_microbit_v2.overlay

Unmodified upstream file from [zephyrproject-rtos/zephyr@413b789deb39](https://github.com/zephyrproject-rtos/zephyr/blob/413b789deb391d3a37d06b463288a5fe765ee57e/samples/boards/bbc/microbit/sound/boards/bbc_microbit_v2.overlay).
License: Apache-2.0. SHA-256: `2034d31e7f7a0c7bfc38ebe32857d5c04d20e541352b26d498c93647b2ede982`.

````text
/ {
	zephyr,user {
		/* period cell corresponds to initial period */
		pwms = <&pwm1 0 PWM_USEC(1500) PWM_POLARITY_NORMAL>;
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
