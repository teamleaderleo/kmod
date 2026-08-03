// SPDX-License-Identifier: LGPL-2.1-or-later

#include "testsuite.h"

static int modprobe_options_config_path(void)
{
	return EXEC_TOOL(modprobe, "-C", "/etc/modprobe config", "mod-loop-a");
}
DEFINE_TEST(modprobe_options_config_path,
	.description = "check recursive modprobe preserves a config path containing a space",
	.config = {
		[TC_UNAME_R] = "4.4.4",
		[TC_ROOTFS] = TESTSUITE_ROOTFS "test-modprobe/install-cmd-loop",
	},
	.env_vars = (const struct keyval[]) {
		{ "MODPROBE", TOOLS_DIR "/modprobe" },
		{ }
	},
	.output = {
		.out = TESTSUITE_ROOTFS "test-modprobe/install-cmd-loop/correct-config-path.txt",
	},
	.modules_loaded = "",
	);

TESTSUITE_MAIN();
