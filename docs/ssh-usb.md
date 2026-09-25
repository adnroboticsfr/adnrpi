# SSH over USB OTG

The ADNRPi One exposes its OTG port as a USB network interface (NCM gadget). A **single cable** powers the board and provides SSH access — no Ethernet, no WiFi needed.

## Connect

1. Plug a USB cable between the **OTG port** of the ADNRPi and your computer
2. Configure the USB network interface on your machine:

**Linux:**

```bash
sudo ip addr add 172.22.1.2/24 dev usb0
sudo ip link set usb0 up
```

**Windows:** The interface appears as "RNDIS/Ethernet Gadget" — assign IP `172.22.1.2` manually (mask `255.255.255.0`).

**macOS:** The interface appears automatically — assign `172.22.1.2` in Network preferences.

1. Connect:

```bash
ssh root@172.22.1.1
```

## Notes

- The board IP is always `172.22.1.1`
- Unplugging the cable also cuts power
- For sustained workloads at 1368 MHz overclock, use a dedicated 5V/2A power supply — a computer USB port may not deliver enough current
