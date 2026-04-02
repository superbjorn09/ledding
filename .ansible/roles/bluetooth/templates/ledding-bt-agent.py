#!/usr/bin/python3
"""Bluetooth agent that auto-accepts pairing and authorizes A2DP connections."""

import dbus
import dbus.service
import dbus.mainloop.glib
from gi.repository import GLib

BUS_NAME = "org.bluez"
AGENT_INTERFACE = "org.bluez.Agent1"
AGENT_PATH = "/ledding/agent"

A2DP_UUID = "0000110d-0000-1000-8000-00805f9b34fb"
AVRCP_UUID = "0000110e-0000-1000-8000-00805f9b34fb"
A2DP_SINK_UUID = "0000110b-0000-1000-8000-00805f9b34fb"

ALLOWED_UUIDS = {A2DP_UUID, AVRCP_UUID, A2DP_SINK_UUID}


class AutoAcceptAgent(dbus.service.Object):
    @dbus.service.method(AGENT_INTERFACE, in_signature="", out_signature="")
    def Release(self):
        print("Agent released")

    @dbus.service.method(AGENT_INTERFACE, in_signature="os", out_signature="")
    def AuthorizeService(self, device, uuid):
        print("AuthorizeService (%s, %s)" % (device, uuid))
        if uuid.lower() in ALLOWED_UUIDS:
            print("  -> Authorized")
            return
        print("  -> Authorized (permissive mode)")
        return

    @dbus.service.method(AGENT_INTERFACE, in_signature="o", out_signature="s")
    def RequestPinCode(self, device):
        print("RequestPinCode (%s) -> 0000" % device)
        return "0000"

    @dbus.service.method(AGENT_INTERFACE, in_signature="o", out_signature="u")
    def RequestPasskey(self, device):
        print("RequestPasskey (%s) -> 0000" % device)
        return dbus.UInt32(0)

    @dbus.service.method(AGENT_INTERFACE, in_signature="ouq", out_signature="")
    def DisplayPasskey(self, device, passkey, entered):
        print("DisplayPasskey (%s, %06u entered %u)" % (device, passkey, entered))

    @dbus.service.method(AGENT_INTERFACE, in_signature="os", out_signature="")
    def DisplayPinCode(self, device, pincode):
        print("DisplayPinCode (%s, %s)" % (device, pincode))

    @dbus.service.method(AGENT_INTERFACE, in_signature="ou", out_signature="")
    def RequestConfirmation(self, device, passkey):
        print("RequestConfirmation (%s, %06d) -> auto-confirmed" % (device, passkey))
        # Auto-trust the device after confirming
        self._trust_device(device)
        return

    @dbus.service.method(AGENT_INTERFACE, in_signature="o", out_signature="")
    def RequestAuthorization(self, device):
        print("RequestAuthorization (%s) -> authorized" % device)
        return

    @dbus.service.method(AGENT_INTERFACE, in_signature="", out_signature="")
    def Cancel(self):
        print("Cancel")

    def _trust_device(self, device_path):
        try:
            bus = dbus.SystemBus()
            device = dbus.Interface(
                bus.get_object(BUS_NAME, device_path),
                "org.freedesktop.DBus.Properties",
            )
            device.Set("org.bluez.Device1", "Trusted", True)
            print("  -> Device trusted: %s" % device_path)
        except Exception as e:
            print("  -> Failed to trust device: %s" % e)


def set_adapter_properties(bus):
    """Ensure the adapter is powered, discoverable and pairable."""
    adapter = dbus.Interface(
        bus.get_object(BUS_NAME, "/org/bluez/hci0"),
        "org.freedesktop.DBus.Properties",
    )
    adapter.Set("org.bluez.Adapter1", "Powered", True)
    adapter.Set("org.bluez.Adapter1", "Discoverable", True)
    adapter.Set("org.bluez.Adapter1", "DiscoverableTimeout", dbus.UInt32(0))
    adapter.Set("org.bluez.Adapter1", "Pairable", True)
    adapter.Set("org.bluez.Adapter1", "Alias", "Ledding Speaker")
    print("Adapter configured: powered, discoverable, pairable")


def main():
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    bus = dbus.SystemBus()

    agent = AutoAcceptAgent(bus, AGENT_PATH)

    manager = dbus.Interface(
        bus.get_object(BUS_NAME, "/org/bluez"),
        "org.bluez.AgentManager1",
    )

    manager.RegisterAgent(AGENT_PATH, "NoInputNoOutput")
    print("Agent registered")

    manager.RequestDefaultAgent(AGENT_PATH)
    print("Default agent set")

    set_adapter_properties(bus)

    print("Waiting for Bluetooth connections...")
    GLib.MainLoop().run()


if __name__ == "__main__":
    main()
