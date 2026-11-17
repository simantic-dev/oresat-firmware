# Upstream

The three ELFs are the OreSat 0.5 card firmware, built from unmodified source.

- Project: OreSat firmware, Portland State Aerospace Society, https://github.com/oresat/oresat-firmware
- Branch: `oresat05-master` (the ChibiOS firmware the OreSat0.5 cards fly; `main` is the Zephyr port)
- Commit: `1494f1cda829d93a8a55fa2629304e33eccbf8bb` (Merge pull request #109, fast-flash-nodeid, 2025-10-24)
- Submodules: `ext/ChibiOS` `d96c2af163e53c456bdd885c52056d20545b6dde`, `ext/CANopenNode` `8c7d852902b2d307e8b91a43332c14e366641e00`
- License: GPL-3.0, copy in `LICENSE-oresat-firmware`. The ELFs are GPL-3.0 binaries of that source; the peers and board
  files in this directory are ours.

Built with `build.sh` (arm-none-eabi-gcc 15.2.1, oresat-configs 0.8.0 generating the object dictionaries). No source file
is edited. Three things differ from the default `make` of each app, all of them make variables the Makefiles define:

- `USE_BOOTLOADER=no` links the app at 0x08000000 (the `*-app-noboot.ld` script) instead of 0x0800A000 behind the
  OreSat bootloader, so the sim, which has no bootloader to jump from, starts at the reset vector.
- `USE_COPT=-DDEBUG_PRINT` on the battery app turns on the debug console on USART2 (the solar app has it on by default).
- `arm-none-eabi-strip -g` removes DWARF (637 KB to 106 KB); code and data are unchanged.
