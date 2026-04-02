#!/bin/bash
# Bluetooth auto-accept agent for Ledding.
# Unblocks rfkill, powers on the adapter, sets it discoverable
# and runs an auto-accept agent for pairing requests.

# Ensure Bluetooth is not rfkill-blocked
rfkill unblock bluetooth
sleep 2

bluetoothctl <<EOF
power on
system-alias "Ledding Speaker"
discoverable on
pairable on
agent NoInputNoOutput
default-agent
EOF

# Keep running so the agent stays active
sleep infinity
