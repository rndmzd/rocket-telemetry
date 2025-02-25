#!/usr/bin/env python3
"""
RFM9x LoRa Module Transceiver Test Script

This script can be run in either transmitter or receiver mode to test
communication between two RFM9x modules. Use this to verify that your
modules can successfully communicate with each other.

Usage:
  - To run as a transmitter: python3 rfm9x_transceiver_test.py --mode tx
  - To run as a receiver: python3 rfm9x_transceiver_test.py --mode rx
"""

import time
import board
import busio
import digitalio
import adafruit_rfm9x
import argparse
import random
import signal
import sys

# Define colors for terminal output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'

# Default settings
DEFAULT_FREQUENCY = 433.0  # MHz
DEFAULT_TX_POWER = 5       # dBm (can be 5-23)
DEFAULT_INTERVAL = 5       # seconds between transmissions

def print_success(message):
    print(f"{GREEN}✓ {message}{RESET}")

def print_error(message):
    print(f"{RED}✗ {message}{RESET}")

def print_info(message):
    print(f"{YELLOW}ℹ {message}{RESET}")

def print_rx(message):
    print(f"{BLUE}← {message}{RESET}")

def print_tx(message):
    print(f"{GREEN}→ {message}{RESET}")

def initialize_rfm9x(frequency=DEFAULT_FREQUENCY, tx_power=DEFAULT_TX_POWER):
    """Initialize the RFM9x module with the specified settings"""
    # Pin configuration (same as in the main application)
    CS = digitalio.DigitalInOut(board.CE1)
    RESET = digitalio.DigitalInOut(board.D25)
    
    # Set pins as outputs
    CS.direction = digitalio.Direction.OUTPUT
    RESET.direction = digitalio.Direction.OUTPUT
    
    # Initialize SPI bus
    spi = busio.SPI(board.SCK, MOSI=board.MOSI, MISO=board.MISO)
    
    # Initialize RFM9x module
    rfm9x = adafruit_rfm9x.RFM9x(spi, CS, RESET, frequency)
    rfm9x.tx_power = tx_power
    
    return rfm9x

def transmitter_mode(args):
    """Run in transmitter mode, sending packets at regular intervals"""
    print_info(f"Starting transmitter mode on frequency {args.frequency} MHz")
    print_info(f"Press Ctrl+C to exit")
    
    try:
        # Initialize the RFM9x module
        rfm9x = initialize_rfm9x(args.frequency, args.tx_power)
        print_success("RFM9x module initialized successfully")
        
        # Counter for sent packets
        packet_counter = 0
        
        while True:
            # Create a test message with a counter and random value
            random_value = random.randint(0, 1000)
            message = f"TEST PKT #{packet_counter} VAL:{random_value}"
            
            # Send the packet
            print_tx(f"Sending: {message}")
            rfm9x.send(bytes(message, "utf-8"))
            
            # Increment counter
            packet_counter += 1
            
            # Wait for the specified interval
            time.sleep(args.interval)
            
    except KeyboardInterrupt:
        print_info("\nTransmitter stopped by user")
    except Exception as e:
        print_error(f"Error in transmitter mode: {e}")

def receiver_mode(args):
    """Run in receiver mode, listening for packets"""
    print_info(f"Starting receiver mode on frequency {args.frequency} MHz")
    print_info(f"Press Ctrl+C to exit")
    
    try:
        # Initialize the RFM9x module
        rfm9x = initialize_rfm9x(args.frequency, args.tx_power)
        print_success("RFM9x module initialized successfully")
        
        # Counter for received packets
        packet_counter = 0
        
        # Start time for calculating reception rate
        start_time = time.time()
        
        while True:
            # Try to receive a packet (with timeout)
            packet = rfm9x.receive(timeout=1.0)
            
            if packet is not None:
                # Increment counter
                packet_counter += 1
                
                # Try to decode the packet
                try:
                    packet_text = packet.decode("utf-8")
                    print_rx(f"Received [{packet_counter}]: {packet_text}")
                    
                    # Calculate and display signal strength
                    rssi = rfm9x.last_rssi
                    print_info(f"Signal strength: {rssi} dBm")
                    
                except UnicodeDecodeError:
                    # If we can't decode as UTF-8, show raw bytes
                    print_rx(f"Received [{packet_counter}]: (raw bytes) {packet}")
                
                # Calculate and show reception rate
                elapsed_time = time.time() - start_time
                rate = packet_counter / elapsed_time * 60
                print_info(f"Reception rate: {rate:.1f} packets/minute")
            
    except KeyboardInterrupt:
        print_info("\nReceiver stopped by user")
    except Exception as e:
        print_error(f"Error in receiver mode: {e}")

def main():
    """Parse arguments and run in the specified mode"""
    parser = argparse.ArgumentParser(
        description="Test RFM9x LoRa module in transmitter or receiver mode"
    )
    
    parser.add_argument(
        "--mode", 
        choices=["tx", "rx"], 
        required=True,
        help="Operating mode: tx (transmitter) or rx (receiver)"
    )
    
    parser.add_argument(
        "--frequency", 
        type=float, 
        default=DEFAULT_FREQUENCY,
        help=f"Frequency in MHz (default: {DEFAULT_FREQUENCY})"
    )
    
    parser.add_argument(
        "--tx-power", 
        type=int, 
        default=DEFAULT_TX_POWER,
        help=f"Transmit power in dBm, 5-23 (default: {DEFAULT_TX_POWER})"
    )
    
    parser.add_argument(
        "--interval", 
        type=float, 
        default=DEFAULT_INTERVAL,
        help=f"Interval between transmissions in seconds (default: {DEFAULT_INTERVAL})"
    )
    
    args = parser.parse_args()
    
    # Run in the specified mode
    if args.mode == "tx":
        transmitter_mode(args)
    else:
        receiver_mode(args)

if __name__ == "__main__":
    main() 