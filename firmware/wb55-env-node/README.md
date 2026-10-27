# wb55-env-node

Firmware for the classr environmental nodes: P-NUCLEO-WB55 USB dongle + SCD30, BLE GATT to the Pi.
This is a trimmed copy of STM32CubeWB (only what the build uses) so the repo stays small.

- `Projects/P-NUCLEO-WB55.USBDongle/Applications/BLE/BLE_EnvNode` - our firmware
  (`scd30.c`, `envs.c`, `env_app.c`; the per-board name is `APPBLE_NODE_NAME` in `STM32_WPAN/App/app_ble.c`).
- `.../BLE/BLE_HeartRate` - the stock ST example, kept to check that the board and BLE stack work.
- `Projects/STM32WB_Copro_Wireless_Binaries` - FUS and BLE stack `.bin` files to flash onto the coprocessor
  (`stm32wb5x_BLE_Stack_full_fw.bin` is required).

Build: STM32CubeIDE > File > Import > Existing Projects > `.../BLE_EnvNode/STM32CubeIDE`, then Clean + Build.
Flash: CubeProgrammer over USB (SW2 on the DFU side), flash `Debug/BLE_EnvNode.hex`, SW2 back to run.

Each board needs a unique `APPBLE_NODE_NAME` (`classr-s1`, `classr-s2`) matching `ENV_NODES` in the Pi's `config.py`.
The 128-bit service UUID is not advertised (it stopped the node from appearing); the Pi finds nodes by name.
