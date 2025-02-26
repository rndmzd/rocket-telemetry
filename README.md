# rocket-telemetry

## Hardware Setup

### Receiver GPS Pinout (Adafruit Ultimate GPS Logger v3)

#### Connection to M0 Adalogger

The Adafruit Ultimate GPS Logger v3 connects to the M0 Adalogger as follows:

| GPS Pin | M0 Adalogger Pin | Description |
|---------|------------------|-------------|
| VIN     | 3.3V            | Power supply (3.3V) |
| GND     | GND             | Ground |
| TX      | RX (Pin 0)      | GPS TX to M0 RX |
| RX      | TX (Pin 1)      | GPS RX to M0 TX |
| EN      | Not Connected   | Enable pin (pulled high internally) |
| VBAT    | Not Connected   | Backup battery (optional) |
| FIX     | Not Connected   | GPS Fix indicator (optional) |
| PPS     | Not Connected   | Pulse Per Second output (optional) |

#### Connection to Raspberry Pi

The Adafruit Ultimate GPS Logger v3 connects to the Raspberry Pi as follows:

| GPS Pin | Raspberry Pi Pin | Description |
|---------|-----------------|-------------|
| VIN     | 3.3V (Pin 1)   | Power supply (3.3V) |
| GND     | GND (Pin 6)    | Ground |
| TX      | RX (Pin 10/GPIO 15) | GPS TX to Pi RX (ttyS0) |
| RX      | TX (Pin 8/GPIO 14)  | GPS RX to Pi TX (ttyS0) |
| EN      | Not Connected  | Enable pin (pulled high internally) |
| VBAT    | Not Connected  | Backup battery (optional) |
| FIX     | Not Connected  | GPS Fix indicator (optional) |
| PPS     | Not Connected  | Pulse Per Second output (optional) |

Note: The GPS module communicates at 9600 baud by default.

Important: For the Raspberry Pi connection, you need to:
1. Enable serial port in raspi-config (but disable serial console)
2. The serial port will be available at `/dev/ttyS0`
3. Make sure the user has permission to access the serial port (add user to 'dialout' group)
