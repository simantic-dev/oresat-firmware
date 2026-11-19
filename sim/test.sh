#!/bin/sh
# Runs the committed OreSat 0.5 card firmware (solar, battery, protocard on three STM32F091RC, one CAN bus)
# for 11 virtual s against the scripted C3 CANopen master. Pass = exit 0: every card boots and goes
# operational, the master's SDO reads return the sensor values, an SDO write changes the solar heartbeat
# to 250 ms, and NMT stop/start works; any fault/panic line fails.
cd "$(dirname "$0")/.." || exit 1
O=$(mktemp); trap 'rm -f "$O"' EXIT
"${SIM:-sim}" run --scenario sim/scenario.yaml --timeout 11 > "$O" 2>&1
rc=0
chk() { if grep -qF -- "$2" "$O"; then echo "ok   $1"; else echo "FAIL $1"; rc=1; fi; }
chk "solar boots and goes operational" "[c3] NMT solar_1(0x0C) operational"
chk "battery boots and goes operational" "[c3] NMT battery_1(0x04) operational"
chk "solar output.voltage read over SDO" "output.voltage = 4800 mV"
chk "battery pack_1.vbatt read over SDO" "pack_1.vbatt = 7400 mV"
chk "SDO write moves solar heartbeat to 250 ms" "[c3] heartbeat solar_1(0x0C) every 250 ms"
chk "NMT stop reaches solar" "[c3] NMT solar_1(0x0C) stopped"
if grep -qiE 'hardfault|panic|guru|fault handler' "$O"; then echo "FAIL fault/panic line seen"; rc=1; else echo "ok   no fault/panic line"; fi
exit $rc
