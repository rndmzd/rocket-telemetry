# Rocket Telemetry Receiver

This is the receiver component of the rocket telemetry system, designed to run on a Raspberry Pi 2W. It receives LoRa transmissions from the rocket and provides a web interface to view the telemetry data in real-time.

## Hardware Requirements

- Raspberry Pi 2W
- RFM95 LoRa module (433MHz)
- Jumper wires

## Wiring

Connect the RFM95 LoRa module to the Raspberry Pi as follows:

```
RFM95 Pin | Raspberry Pi Pin
-----------|----------------
VIN        | 3.3V
GND        | GND
SCK        | SCK (GPIO11)
MISO       | MISO (GPIO9)
MOSI       | MOSI (GPIO10)
CS         | CE1 (GPIO7)
RST        | GPIO25
```

## Software Setup

1. Install system dependencies:
   ```bash
   sudo apt-get update
   sudo apt-get install -y python3-pip python3-venv
   ```

2. Enable SPI interface:
   ```bash
   sudo raspi-config
   # Navigate to Interface Options > SPI > Enable
   ```

3. Set up Python virtual environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

4. Configure WiFi hotspot:
   ```bash
   sudo apt-get install -y hostapd dnsmasq
   sudo systemctl unmask hostapd
   sudo systemctl enable hostapd
   ```

5. Edit `/etc/dhcpcd.conf`:
   ```
   interface wlan0
   static ip_address=192.168.4.1/24
   nohook wpa_supplicant
   ```

6. Edit `/etc/hostapd/hostapd.conf`:
   ```
   interface=wlan0
   driver=nl80211
   ssid=RocketTelemetry
   hw_mode=g
   channel=7
   wmm_enabled=0
   macaddr_acl=0
   auth_algs=1
   ignore_broadcast_ssid=0
   wpa=2
   wpa_passphrase=rocketpass
   wpa_key_mgmt=WPA-PSK
   wpa_pairwise=TKIP
   rsn_pairwise=CCMP
   ```

7. Edit `/etc/dnsmasq.conf`:
   ```
   interface=wlan0
   dhcp-range=192.168.4.2,192.168.4.20,255.255.255.0,24h
   ```

8. Set up autostart service:
   ```bash
   # Copy files to home directory
   sudo mkdir -p /home/pi/rocket-telemetry
   sudo cp -r . /home/pi/rocket-telemetry/
   
   # Install the service
   sudo cp rocket-telemetry.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable rocket-telemetry
   sudo systemctl start rocket-telemetry
   ```

9. Reboot the Raspberry Pi:
   ```bash
   sudo reboot
   ```

## Running the Application

The application will start automatically when the Raspberry Pi boots up. You can check its status with:
```bash
sudo systemctl status rocket-telemetry
```

To manually start/stop the service:
```bash
sudo systemctl start rocket-telemetry
sudo systemctl stop rocket-telemetry
```

To view the logs:
```bash
sudo journalctl -u rocket-telemetry -f
```

## Accessing the Web Interface

1. Connect to the "RocketTelemetry" WiFi network using password "rocketpass"
2. Open a web browser and navigate to `http://192.168.4.1`

## Features

- Real-time GPS tracking on an interactive map
- Live telemetry data display including:
  - GPS coordinates and altitude
  - Accelerometer readings
  - Gyroscope readings
  - Pressure and temperature
- Automatic path tracking
- Mobile-responsive design
- Automatic startup on boot
- Service auto-restart on failure

## Troubleshooting

1. If the LoRa module is not detected:
   - Check the wiring connections
   - Verify SPI is enabled: `ls /dev/spi*`
   - Check permissions: `sudo usermod -a -G spi,gpio $USER`

2. If the WiFi hotspot is not working:
   - Check hostapd status: `sudo systemctl status hostapd`
   - Verify network interface: `ifconfig wlan0`
   - Check logs: `sudo journalctl -u hostapd`

3. If the receiver service isn't starting:
   - Check service status: `sudo systemctl status rocket-telemetry`
   - Check logs: `sudo journalctl -u rocket-telemetry -f`
   - Verify file permissions: `ls -l /home/pi/rocket-telemetry`
   - Check Python environment: `ls -l /home/pi/rocket-telemetry/receiver/venv` 