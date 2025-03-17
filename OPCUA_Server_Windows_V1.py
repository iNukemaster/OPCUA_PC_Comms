import csv
import time
import os
from datetime import datetime
from pymodbus.client import ModbusTcpClient, ModbusSerialClient
from flask import Flask, render_template
from flask_socketio import SocketIO
import threading
from opcua import Server

# ==================== CONFIGURATION ====================
MODBUS_TYPE = "rtu"  # Change to "tcp" if using Ethernet
PLC_IP = "192.168.1.10"  # PLC's IP Address
PLC_PORT = 502  # Modbus TCP Port
SERIAL_PORT = "COM8"  # Serial Port
BAUDRATE = 9600
PARITY = "O"
STOPBITS = 1
BYTESIZE = 8
TIMEOUT = 1
REGISTER_ADDRESS = 0x6304
REGISTER_COUNT = 1
UNIT_ID = 1
CSV_FILE = "plc_data.csv"
LOG_INTERVAL = 5
MAX_RECONNECT_ATTEMPTS = 3

# Flask and Socket.IO
app = Flask(__name__)
socketio = SocketIO(app)
latest_data = None

# ==================== OPC UA SERVER ====================
server = Server()
server.set_endpoint("opc.tcp://10.241.155.248:4840")
server.set_server_name("MacBook OPC UA Server")
uri = "http://macbook-opcua"
idx = server.register_namespace(uri)
timestamp_node = server.nodes.objects.add_variable(idx, "Timestamp", "")
timestamp_node.set_writable()
server.start()
print("✅ OPC UA Server started")

# ==================== CONNECT TO PLC ====================
def connect_to_plc():
    try:
        if MODBUS_TYPE == "tcp":
            client = ModbusTcpClient(PLC_IP, port=PLC_PORT)
        else:
            client = ModbusSerialClient(port=SERIAL_PORT, baudrate=BAUDRATE, parity=PARITY,
                                        stopbits=STOPBITS, bytesize=BYTESIZE, timeout=TIMEOUT)
        return client if client.connect() else None
    except Exception as e:
        print(f"❌ PLC Connection Error: {e}")
        return None

# ==================== READ DATA FROM PLC ====================
def read_plc_data(client):
    try:
        response = client.read_coils(address=6304, count=1)
        return response.bits if not response.isError() else None
    except Exception as e:
        print(f"❌ PLC Read Error: {e}")
        return None

# ==================== SAVE DATA TO CSV ====================
def initialize_csv():
    if not os.path.exists(CSV_FILE):
        with open(CSV_FILE, "w", newline="") as file:
            csv.writer(file).writerow(["Timestamp", f"Register_{REGISTER_ADDRESS}"])
        print("✅ CSV Initialized")

def save_to_csv(data):
    if data:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(CSV_FILE, "a", newline="") as file:
            csv.writer(file).writerow([timestamp] + data)
        print(f"✅ Logged Data: {data}")

# ==================== MODBUS THREAD ====================
def modbus_thread():
    global latest_data
    client = connect_to_plc()
    if not client:
        for _ in range(MAX_RECONNECT_ATTEMPTS):
            time.sleep(5)
            client = connect_to_plc()
            if client:
                break
        if not client:
            print("Failed to connect. Exiting.")
            return
    
    print("📡 Logging started...")
    try:
        while True:
            data = read_plc_data(client)
            if data is None:
                print("⚠ Connection lost, attempting to reconnect...")
                client.close()
                client = connect_to_plc()
                if not client:
                    break
                continue
            latest_data = data
            socketio.emit('update_data', {'data': data})
            save_to_csv(data)
            timestamp_node.set_value(datetime.now().isoformat())
            time.sleep(LOG_INTERVAL)
    except KeyboardInterrupt:
        print("🛑 Stopping...")
    finally:
        if client:
            client.close()
        server.stop()
        print("Server Stopped.")

# ==================== FLASK ROUTES ====================
@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('connect')
def handle_connect():
    if latest_data is not None:
        socketio.emit('update_data', {'data': latest_data})

# ==================== MAIN ====================
if __name__ == "__main__":
    initialize_csv()
    threading.Thread(target=modbus_thread, daemon=True).start()
    socketio.run(app, host='0.0.0.0', port=5000)