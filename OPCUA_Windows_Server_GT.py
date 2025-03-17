from opcua import Server
from datetime import datetime
import time

# Create OPC UA Server
server = Server()

# Set Endpoint - Use your actual Windows laptop IP
server.set_endpoint("opc.tcp://172.20.10.12:4840")

# Set Server Name
server.set_server_name("Windows Laptop OPC UA Server")

# Create a new namespace
uri = "http://windows-opcua"
idx = server.register_namespace(uri)

# Add a variable node for timestamp
timestamp_node = server.nodes.objects.add_variable(idx, "Timestamp", "")

# Set the variable to be writable
timestamp_node.set_writable()

# Start the server
server.start()
print("✅ OPC UA Server started on opc.tcp://172.20.10.12:4840")

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
