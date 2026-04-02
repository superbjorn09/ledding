#!/bin/bash
# Bluetooth setup for Ledding.
# Unblocks rfkill, powers on the adapter, sets it discoverable
# and starts the auto-accept agent.

# Ensure Bluetooth is not rfkill-blocked
rfkill unblock bluetooth
sleep 2

# Power on and configure
bluetoothctl --timeout 3 power on
bluetoothctl --timeout 3 system-alias "Ledding Speaker"
bluetoothctl --timeout 3 discoverable on
bluetoothctl --timeout 3 pairable on

# Start Python agent that auto-accepts all pairing requests
exec /usr/local/bin/ledding-bt-agent.py
