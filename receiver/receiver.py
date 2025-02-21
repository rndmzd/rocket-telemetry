from flask import Flask, render_template, jsonify
import threading
import time
import json
import board
import busio
import digitalio
import adafruit_rfm9x
from threading import Lock

# Initialize Flask app
app = Flask(__name__)

# Configure RFM95 / LoRa radio
CS = digitalio.DigitalInOut(board.CE1)
RESET = digitalio.DigitalInOut(board.D25)
spi = busio.SPI(board.SCK, MOSI=board.MOSI, MISO=board.MISO)

# Initialize RFM radio
rfm9x = adafruit_rfm9x.RFM9x(spi, CS, RESET, 433.0)
rfm9x.tx_power = 2

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
data_lock = Lock()

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

@app.route('/data')
def get_data():
    """API endpoint to get latest telemetry data"""
    with data_lock:
        return jsonify(latest_data)

if __name__ == '__main__':
    # Start LoRa receiver thread
    receiver_thread = threading.Thread(target=lora_receiver, daemon=True)
    receiver_thread.start()
    
    # Start Flask server
    app.run(host='0.0.0.0', port=80, debug=True, use_reloader=False) 