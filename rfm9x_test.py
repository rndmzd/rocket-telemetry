#!/usr/bin/env python3
"""
RFM9x LoRa Module Wiring Test Script

This script tests if the RFM9x LoRa module is correctly wired to the Raspberry Pi.
It attempts to initialize the module and perform basic operations to verify functionality.
"""

import time
import board
import busio
import digitalio
import adafruit_rfm9x

# Define colors for terminal output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
RESET = '\033[0m'

def print_success(message):
    print(f"{GREEN}✓ {message}{RESET}")

def print_error(message):
    print(f"{RED}✗ {message}{RESET}")

def print_info(message):
    print(f"{YELLOW}ℹ {message}{RESET}")

def test_rfm9x_wiring():
    print_info("Starting RFM9x LoRa module wiring test...")
    
    # Pin configuration (same as in the main application)
    CS = digitalio.DigitalInOut(board.CE1)
    RESET = digitalio.DigitalInOut(board.D25)
    
    # Set pins as outputs
    try:
        CS.direction = digitalio.Direction.OUTPUT
        RESET.direction = digitalio.Direction.OUTPUT
        print_success("GPIO pins configured successfully")
    except Exception as e:
        print_error(f"Failed to configure GPIO pins: {e}")
        return False
    
    # Initialize SPI bus
    try:
        spi = busio.SPI(board.SCK, MOSI=board.MOSI, MISO=board.MISO)
        print_success("SPI bus initialized successfully")
    except Exception as e:
        print_error(f"Failed to initialize SPI bus: {e}")
        return False
    
    # Initialize RFM9x module
    try:
        # Default frequency 433.0 MHz
        rfm9x = adafruit_rfm9x.RFM9x(spi, CS, RESET, 433.0)
        print_success("RFM9x module initialized successfully")
        
        # Set transmit power (5 to 23 dBm)
        rfm9x.tx_power = 5
        print_success("Transmit power set successfully")
        
        # Read the temperature from the module (basic functionality test)
        temp = rfm9x.temperature
        print_success(f"Module temperature read: {temp}°C")
        
        # Try to send a test packet
        print_info("Sending test packet...")
        rfm9x.send(bytes("HELLO WORLD!", "utf-8"))
        print_success("Test packet sent successfully")
        
        # Try to receive (with a short timeout)
        print_info("Listening for packets (5 seconds)...")
        packet = rfm9x.receive(timeout=5.0)
        if packet is not None:
            print_success(f"Received packet: {packet}")
        else:
            print_info("No packet received (this is normal if no transmitter is active)")
        
        return True
        
    except Exception as e:
        print_error(f"Failed to initialize or communicate with RFM9x module: {e}")
        print_info("Check your wiring connections:")
        print_info("- Make sure the module is properly connected to power (3.3V and GND)")
        print_info("- Verify SPI connections (MOSI, MISO, SCK)")
        print_info("- Check CS (CE1) and RESET (D25) connections")
        print_info("- Ensure the antenna is properly attached")
        return False

if __name__ == "__main__":
    try:
        if test_rfm9x_wiring():
            print_info("All tests passed! The RFM9x module appears to be wired correctly.")
        else:
            print_error("Some tests failed. Please check your wiring and try again.")
    except KeyboardInterrupt:
        print_info("\nTest interrupted by user.")
    except Exception as e:
        print_error(f"Unexpected error: {e}") 