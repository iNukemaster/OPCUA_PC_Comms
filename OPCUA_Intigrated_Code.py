import csv
import time
import os
import threading
from datetime import datetime
from pymodbus.client import ModbusTcpClient, ModbusSerialClient
from flask import Flask, render_template
from flask_socketio import SocketIO
from opcua import Server

# ==================== CONFIGURATION ====================

MODBUS_TYPE = "rtu"  # "tcp" for Ethernet, "rtu" for Serial
PLC_IP = "192.168.1.10"
PLC_PORT = 502

SERIAL_PORT = "COM8"
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

# Flask App
app = Flask(__name__)
socketio = SocketIO(app)
latest_data = None

# ==================== OPC UA SERVER SETUP ====================
opcua_server = Server()
opcua_server.set_endpoint("opc.tcp://172.20.10.12:4840")
opcua_server.set_server_name("Windows Laptop OPC UA Server")
uri = "http://windows-opcua"
idx = opcua_server.register_namespace(uri)
timestamp_node = opcua_server.nodes.objects.add_variable(idx, "Timestamp", "")
timestamp_node.set_writable()

# ==================== CSV INITIALIZATION ====================
def initialize_csv():
    if not os.path.exists(CSV_FILE):
        with open(CSV_FILE, mode="w", newline="") as file:
            writer = csv.writer(file)
            headers = ["Timestamp"] + [f"Register_{REGISTER_ADDRESS + i}" for i in range(REGISTER_COUNT)]
            writer.writerow(headers)
        print(f"✅ Created new CSV file: {CSV_FILE}")

def save_to_csv(data):
    if data is None:
        print("⚠ No data to save")
        return
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(CSV_FILE, mode="a", newline="") as file:
        writer = csv.writer(file)
        writer.writerow([timestamp] + data)
    print(f"✅ Data logged at {timestamp}: {data}")

# ==================== MODBUS CONNECTION ====================
def connect_to_plc():
    try:
        if MODBUS_TYPE == "tcp":
            client = ModbusTcpClient(PLC_IP, port=PLC_PORT)
        else:
            client = ModbusSerialClient(
                port=SERIAL_PORT,
                baudrate=BAUDRATE,
                parity=PARITY,
                stopbits=STOPBITS,
                bytesize=BYTESIZE,
                timeout=TIMEOUT,
            )
        if client.connect():
            print(f"✅ Connected to PLC via Modbus {MODBUS_TYPE.upper()}")
            return client
        else:
            print("❌ Failed to connect to PLC")
            return None
    except Exception as e:
        print(f"❌ Exception while connecting to PLC: {str(e)}")
        return None

def read_plc_data(client):
    try:
        response = client.read_coils(address=REGISTER_ADDRESS, count=REGISTER_COUNT, unit=UNIT_ID)
        if response.isError():
            print(f"❌ Modbus Error: {response}")
            return None
        return response.bits
    except Exception as e:
        print(f"❌ Exception while reading PLC: {str(e)}")
        return None

# ==================== MODBUS + OPC UA + CSV + SOCKET.IO ====================
def modbus_thread():
    global latest_data

    client = connect_to_plc()
    if client is None:
        retry_count = 0
        while client is None and retry_count < MAX_RECONNECT_ATTEMPTS:
            print(f"Retrying connection ({retry_count + 1}/{MAX_RECONNECT_ATTEMPTS})...")
            time.sleep(5)
            retry_count += 1
            client = connect_to_plc()
        if client is None:
            print("Failed to connect after multiple attempts. Exiting thread.")
            return

    print("📡 Starting Modbus + OPC UA + Web logging...")

    try:
        reconnect_count = 0
        while True:
            data = read_plc_data(client)

            if data is None:
                if reconnect_count < MAX_RECONNECT_ATTEMPTS:
                    print(f"Reconnecting... ({reconnect_count + 1}/{MAX_RECONNECT_ATTEMPTS})")
                    client.close()
                    time.sleep(2)
                    client = connect_to_plc()
                    reconnect_count += 1
                    continue
                else:
                    print("Too many failed reads. Exiting thread.")
                    break
            else:
                reconnect_count = 0
                latest_data = data
                socketio.emit('update_data', {'data': data})
                save_to_csv(data)

                # Update OPC UA server
                current_time = datetime.now().isoformat()
                timestamp_node.set_value(current_time)
                print(f"📤 OPC UA Timestamp updated: {current_time}")

            time.sleep(LOG_INTERVAL)

    except KeyboardInterrupt:
        print("🛑 Stopping data collection thread...")
    finally:
        if client is not None:
            client.close()
        print("Modbus connection closed.")

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

    # Start OPC UA Server
    opcua_server.start()
    print("✅ OPC UA Server started at opc.tcp://172.20.10.12:4840")

    try:
        # Start Modbus + Data Logging Thread
        threading.Thread(target=modbus_thread, daemon=True).start()

        # Start Flask Web App
        socketio.run(app, host='0.0.0.0', port=5000)

    except KeyboardInterrupt:
        print("🛑 Server shutdown requested.")

    finally:
        opcua_server.stop()
        print("✅ OPC UA Server stopped.")