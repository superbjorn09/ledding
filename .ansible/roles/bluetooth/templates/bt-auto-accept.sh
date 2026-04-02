#!/bin/bash
# Bluetooth setup for Ledding.
# Unblocks rfkill and starts the auto-accept agent
# which handles all adapter configuration via D-Bus.

rfkill unblock bluetooth
sleep 2

exec /usr/local/bin/ledding-bt-agent.py
