#!/bin/bash
# Bluetooth auto-accept agent for Ledding.
# Keeps the Pi discoverable and auto-accepts pairing requests.

bluetoothctl <<EOF
power on
discoverable on
pairable on
agent NoInputNoOutput
default-agent
EOF

# Keep running so the agent stays active
sleep infinity
