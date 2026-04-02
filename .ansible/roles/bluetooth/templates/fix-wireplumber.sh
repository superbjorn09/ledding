#!/bin/bash
# Re-apply WirePlumber seat-monitoring patch after package upgrades.
# WirePlumber 0.5 on Trixie does not support conf.d overrides for
# component dependencies, so we must patch the vendor config directly.
sed -i 's/^\(\s*\)wants = \[ monitor\.bluez\.seat-monitoring \]/\1# wants = [ monitor.bluez.seat-monitoring ]/' \
    /usr/share/wireplumber/wireplumber.conf 2>/dev/null || true
