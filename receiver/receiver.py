from flask import Flask, render_template, jsonify, request, redirect, url_for
import threading
import time
import json
import board
import busio
import digitalio
import adafruit_rfm9x
import adafruit_gps
import serial
from threading import Lock
import os
import math

# Initialize Flask app
app = Flask(__name__)

# Settings file path
SETTINGS_FILE = 'settings.json'

# Default settings
DEFAULT_SETTINGS = {
    'frequency': 433.0,
    'tx_power': 5,
    'gps_baudrate': 9600
}

# Global variables
gps = None
rfm9x = None
data_lock = Lock()
settings_lock = Lock()
lora_lock = Lock()

# Global variables to store latest data
latest_data = {
    'gps': {'lat': 0, 'lng': 0, 'alt': 0},
    'imu': {
        'acc': {'x': 0, 'y': 0, 'z': 0},
        'mag': {'x': 0, 'y': 0, 'z': 0},
        'gyro': {'x': 0, 'y': 0, 'z': 0},
        'pressure': 0,
        'temp': 0
    },
    'receiver_gps': {'lat': 0, 'lng': 0, 'alt': 0},
    'distance': 0,
    'timestamp': 0
}

def calculate_distance(lat1, lon1, lat2, lon2):
    """Calculate distance between two points in meters using Haversine formula"""
    R = 6371000  # Earth's radius in meters

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = math.sin(delta_phi/2) * math.sin(delta_phi/2) + \
        math.cos(phi1) * math.cos(phi2) * \
        math.sin(delta_lambda/2) * math.sin(delta_lambda/2)
    
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    distance = R * c

    return distance

def initialize_gps(baudrate):
    """Initialize GPS module"""
    uart = serial.Serial("/dev/ttyS0", baudrate=baudrate, timeout=10)
    gps_module = adafruit_gps.GPS(uart, debug=False)
    
    # Initialize the GPS module
    gps_module.send_command(b'PMTK314,0,1,0,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0')
    gps_module.send_command(b'PMTK220,1000')
    
    return gps_module

def gps_receiver():
    """Background thread to receive GPS data"""
    global gps
    
    while True:
        try:
            if gps is None:
                time.sleep(1)
                continue

            gps.update()
            if not gps.has_fix:
                time.sleep(0.1)
                continue

            with data_lock:
                latest_data['receiver_gps'].update({
                    'lat': gps.latitude,
                    'lng': gps.longitude,
                    'alt': gps.altitude_m if gps.altitude_m is not None else 0
                })
                
                # Calculate distance if we have both positions
                if latest_data['gps']['lat'] != 0 and latest_data['gps']['lng'] != 0:
                    latest_data['distance'] = calculate_distance(
                        latest_data['gps']['lat'],
                        latest_data['gps']['lng'],
                        latest_data['receiver_gps']['lat'],
                        latest_data['receiver_gps']['lng']
                    )

        except Exception as e:
            print(f"Error reading GPS: {e}")
            time.sleep(1)

def load_settings():
    """Load settings from file or create with defaults"""
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, 'r') as f:
                settings = json.load(f)
                # Ensure all default settings exist
                for key, value in DEFAULT_SETTINGS.items():
                    if key not in settings:
                        settings[key] = value
                return settings
        except:
            return DEFAULT_SETTINGS.copy()
    return DEFAULT_SETTINGS.copy()

def save_settings(settings):
    """Save settings to file"""
    with open(SETTINGS_FILE, 'w') as f:
        json.dump(settings, f)

def initialize_lora(frequency, tx_power):
    """Initialize or reinitialize LoRa radio with given settings"""
    global rfm9x
    
    # Set up thread safety
    with lora_lock:
        # Configure RFM95 / LoRa radio
        CS = digitalio.DigitalInOut(board.CE1)
        RESET = digitalio.DigitalInOut(board.D25)
        
        # Explicitly set the pins as outputs
        CS.direction = digitalio.Direction.OUTPUT
        RESET.direction = digitalio.Direction.OUTPUT
        
        spi = busio.SPI(board.SCK, MOSI=board.MOSI, MISO=board.MISO)

        # Clean up old instance if it exists
        if rfm9x is not None:
            # Clean up old instance if it exists
            try:
                rfm9x.deinit()
            except Exception as e:
                print(f"Error deinitializing RFM9x: {e}")
                
        # Initialize RFM radio with a small delay to ensure stability
        time.sleep(0.1)  
        rfm9x = adafruit_rfm9x.RFM9x(spi, CS, RESET, frequency)
        rfm9x.tx_power = tx_power
        
        # Give the module time to stabilize
        time.sleep(0.1)
        
        return rfm9x

def parse_gps_packet(packet):
    """Parse GPS data from packet string"""
    try:
        parts = packet.decode().split(',')
        data = {}
        for part in parts:
            key, value = part.split('=')
            if key == 'LAT':
                data['lat'] = float(value)
            elif key == 'LNG':
                data['lng'] = float(value)
            elif key == 'ALT':
                data['alt'] = float(value)
        return data
    except:
        return None

def parse_imu_packet(packet):
    """Parse IMU data from packet string"""
    try:
        parts = packet.decode().split(',')
        data = {'acc': {}, 'mag': {}, 'gyro': {}}
        
        for part in parts:
            key, value = part.split('=')
            if key == 'ACC':
                x, y, z = value.split(';')
                data['acc'] = {'x': float(x), 'y': float(y), 'z': float(z)}
            elif key == 'MAG':
                x, y, z = value.split(';')
                data['mag'] = {'x': float(x), 'y': float(y), 'z': float(z)}
            elif key == 'GYRO':
                x, y, z = value.split(';')
                data['gyro'] = {'x': float(x), 'y': float(y), 'z': float(z)}
            elif key == 'PRES':
                data['pressure'] = float(value)
            elif key == 'TEMP':
                data['temp'] = float(value)
        return data
    except:
        return None

def lora_receiver():
    """Background thread to receive LoRa packets"""
    global rfm9x
    while True:
        if rfm9x is None:
            time.sleep(1)
            continue
        
        try:
            packet = rfm9x.receive(timeout=1.0)
            if packet:
                try:
                    # Try to parse as GPS data first
                    gps_data = parse_gps_packet(packet)
                    if gps_data:
                        with data_lock:
                            latest_data['gps'].update(gps_data)
                            latest_data['timestamp'] = time.time()
                    else:
                        # Try to parse as IMU data
                        imu_data = parse_imu_packet(packet)
                        if imu_data:
                            with data_lock:
                                latest_data['imu'].update(imu_data)
                                latest_data['timestamp'] = time.time()
                except Exception as e:
                    print(f"Error parsing packet: {e}")
        except Exception as e:
            print(f"Error in LoRa receiver: {e}")
            time.sleep(1)

@app.route('/')
def index():
    """Serve the main page"""
    return render_template('index.html')

@app.route('/settings', methods=['GET', 'POST'])
def settings():
    """Handle settings page"""
    if request.method == 'POST':
        try:
            # Extract settings from form
            frequency = float(request.form.get('lora_frequency', 433.0))
            tx_power = int(request.form.get('lora_power', 20))
            gps_baudrate = int(request.form.get('gps_baudrate', 9600))
            
            # Update settings
            new_settings = {
                'frequency': frequency,
                'tx_power': tx_power,
                'gps_baudrate': gps_baudrate
            }
            save_settings(new_settings)
            
            # Update LoRa settings
            initialize_lora(frequency, tx_power)
            
            # Load updated settings
            settings = load_settings()
            return render_template('settings.html', 
                                current_frequency=settings['frequency'],
                                current_tx_power=settings['tx_power'],
                                current_gps_baudrate=settings['gps_baudrate'],
                                status='Settings updated successfully')
        except Exception as e:
            settings = load_settings()
            return render_template('settings.html', 
                                current_frequency=settings['frequency'],
                                current_tx_power=settings['tx_power'],
                                current_gps_baudrate=settings['gps_baudrate'],
                                status=f"Error: {str(e)}", 
                                error=True)
    
    # GET request
    settings = load_settings()
    return render_template('settings.html', 
                         current_frequency=settings['frequency'],
                         current_tx_power=settings['tx_power'],
                         current_gps_baudrate=settings['gps_baudrate'])

@app.route('/data')
def get_data():
    """API endpoint to get latest telemetry data"""
    with data_lock:
        return jsonify(latest_data)

if __name__ == '__main__':
    # Load initial settings
    initial_settings = load_settings()
    
    # Initialize hardware
    initialize_lora(initial_settings['frequency'], initial_settings['tx_power'])
    gps = initialize_gps(initial_settings['gps_baudrate'])
    
    # Start LoRa receiver thread
    receiver_thread = threading.Thread(target=lora_receiver, daemon=True)
    receiver_thread.start()
    
    # Start GPS receiver thread
    gps_thread = threading.Thread(target=gps_receiver, daemon=True)
    gps_thread.start()
    
    # Start Flask server
    app.run(host='0.0.0.0', port=80, debug=True, use_reloader=False) 