from flask import Flask, render_template, jsonify, request, redirect, url_for
import threading
import time
import json
import board
import busio
import digitalio
import adafruit_rfm9x
import os
from threading import Lock

# Initialize Flask app
app = Flask(__name__)

# Settings file path
SETTINGS_FILE = 'settings.json'

# Default settings
DEFAULT_SETTINGS = {
    'frequency': 433.0,
    'tx_power': 2
}

# Global variables
rfm9x = None
data_lock = Lock()
settings_lock = Lock()

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
    'timestamp': 0
}

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
    
    # Configure RFM95 / LoRa radio
    CS = digitalio.DigitalInOut(board.CE1)
    RESET = digitalio.DigitalInOut(board.D25)
    spi = busio.SPI(board.SCK, MOSI=board.MOSI, MISO=board.MISO)

    # Initialize RFM radio
    if rfm9x is not None:
        # Clean up old instance if it exists
        rfm9x.deinit()
    
    rfm9x = adafruit_rfm9x.RFM9x(spi, CS, RESET, frequency)
    rfm9x.tx_power = tx_power
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
    while True:
        if rfm9x is None:
            time.sleep(1)
            continue
            
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

@app.route('/')
def index():
    """Serve the main page"""
    return render_template('index.html')

@app.route('/settings', methods=['GET', 'POST'])
def settings():
    """Handle settings page"""
    if request.method == 'POST':
        try:
            new_frequency = float(request.form['frequency'])
            new_tx_power = int(request.form['tx_power'])
            
            if not (400 <= new_frequency <= 500):
                raise ValueError("Frequency must be between 400 and 500 MHz")
            if not (2 <= new_tx_power <= 20):
                raise ValueError("TX Power must be between 2 and 20 dB")
            
            with settings_lock:
                settings = load_settings()
                settings['frequency'] = new_frequency
                settings['tx_power'] = new_tx_power
                save_settings(settings)
                
                # Reinitialize hardware
                initialize_lora(new_frequency, new_tx_power)
            
            return render_template('settings.html', 
                                current_frequency=new_frequency,
                                current_tx_power=new_tx_power,
                                status="Settings updated successfully")
        except Exception as e:
            settings = load_settings()
            return render_template('settings.html', 
                                current_frequency=settings['frequency'],
                                current_tx_power=settings['tx_power'],
                                status=f"Error: {str(e)}", 
                                error=True)
    
    # GET request
    settings = load_settings()
    return render_template('settings.html', 
                         current_frequency=settings['frequency'],
                         current_tx_power=settings['tx_power'])

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
    
    # Start LoRa receiver thread
    receiver_thread = threading.Thread(target=lora_receiver, daemon=True)
    receiver_thread.start()
    
    # Start Flask server
    app.run(host='0.0.0.0', port=80, debug=True, use_reloader=False) 