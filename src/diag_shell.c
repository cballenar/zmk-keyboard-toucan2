/*
 * Diagnostic shell commands for the Toucan (only built with
 * CONFIG_TOUCAN_DIAG_SHELL, see snippets/toucan-diag-shell).
 */

#include <zephyr/kernel.h>
#include <zephyr/shell/shell.h>
#include <zephyr/sys/reboot.h>

/* Same magic ZMK's &bootloader behavior uses (RST_UF2) for the
 * Adafruit/Seeed nRF52 UF2 bootloader. */
#define TOUCAN_RST_UF2 0x57

static int cmd_dfu(const struct shell *sh, size_t argc, char **argv) {
    shell_print(sh, "rebooting into UF2 bootloader...");
    k_sleep(K_MSEC(100));
    sys_reboot(TOUCAN_RST_UF2);
    return 0;
}

SHELL_CMD_REGISTER(dfu, NULL, "Reboot into the UF2 bootloader", cmd_dfu);
