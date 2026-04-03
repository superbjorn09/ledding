#!/usr/bin/python3
"""Bluetooth agent that auto-accepts pairing, authorizes A2DP connections,
and auto-reconnects known devices."""

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
            device = dbus.Interface(
                self.connection.get_object(BUS_NAME, device_path),
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


def reconnect_known_devices(bus):
    """Try to connect all trusted, paired devices."""
    try:
        managed = dbus.Interface(
            bus.get_object(BUS_NAME, "/"),
            "org.freedesktop.DBus.ObjectManager",
        )
        for path, interfaces in managed.GetManagedObjects().items():
            if "org.bluez.Device1" not in interfaces:
                continue
            props = interfaces["org.bluez.Device1"]
            if props.get("Trusted", False) and props.get("Paired", False):
                if not props.get("Connected", False):
                    alias = props.get("Alias", path)
                    try:
                        device = dbus.Interface(
                            bus.get_object(BUS_NAME, path),
                            "org.bluez.Device1",
                        )
                        print("Reconnecting: %s" % alias)
                        device.Connect()
                        print("  -> Connected: %s" % alias)
                    except Exception as e:
                        print("  -> Failed to connect %s: %s" % (alias, e))
    except Exception as e:
        print("reconnect_known_devices failed: %s" % e)


def on_properties_changed(interface, changed, invalidated, path=None):
    """React to adapter property changes — reconnect devices when adapter powers on."""
    if interface == "org.bluez.Adapter1" and changed.get("Powered", False):
        print("Adapter powered on, reconnecting known devices...")
        try:
            bus = dbus.SystemBus()
            reconnect_known_devices(bus)
        except Exception as e:
            print("Reconnect on power-on failed: %s" % e)


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

    # Auto-trust all paired devices
    adapter_obj = bus.get_object(BUS_NAME, "/")
    managed = dbus.Interface(adapter_obj, "org.freedesktop.DBus.ObjectManager")
    for path, interfaces in managed.GetManagedObjects().items():
        if "org.bluez.Device1" in interfaces:
            props = interfaces["org.bluez.Device1"]
            if props.get("Paired", False) and not props.get("Trusted", False):
                device = dbus.Interface(
                    bus.get_object(BUS_NAME, path),
                    "org.freedesktop.DBus.Properties",
                )
                device.Set("org.bluez.Device1", "Trusted", True)
                print("Auto-trusted paired device: %s" % props.get("Alias", path))

    # Listen for adapter property changes (e.g. power-on after crash)
    bus.add_signal_receiver(
        on_properties_changed,
        dbus_interface="org.freedesktop.DBus.Properties",
        signal_name="PropertiesChanged",
        path_keyword="path",
    )

    # Try to reconnect known devices at startup
    reconnect_known_devices(bus)

    # Periodically retry reconnecting (every 30s)
    def periodic_reconnect():
        reconnect_known_devices(bus)
        return True
    GLib.timeout_add_seconds(30, periodic_reconnect)

    print("Waiting for Bluetooth connections...")
    GLib.MainLoop().run()


if __name__ == "__main__":
    main()
