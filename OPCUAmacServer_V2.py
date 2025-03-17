from opcua import Server
from datetime import datetime
import time
import socket

# Get the local IP address automatically
hostname = socket.gethostname()
local_ip = socket.gethostbyname(hostname)

# Create OPC UA Server
server = Server()

# Set Endpoint dynamically
endpoint = f"opc.tcp://{local_ip}:4840"
server.set_endpoint(endpoint)

# Set Server Name
server.set_server_name("MacBook OPC UA Server")

# Create a new namespace
uri = "http://macbook-opcua"
idx = server.register_namespace(uri)

# Add a variable node for timestamp
timestamp_node = server.nodes.objects.add_variable(idx, "Timestamp", "")

# Set the variable to be writable
timestamp_node.set_writable()

# Start the server
server.start()
print(f"✅ OPC UA Server started on {endpoint}")

try:
    while True:
        # Update timestamp every second
        current_time = datetime.now().isoformat()
        timestamp_node.set_value(current_time)
        print(f"Updated Timestamp: {current_time}")
        time.sleep(1)

except KeyboardInterrupt:
    print("Stopping Server...")
    server.stop()
    print("Server Stopped.")