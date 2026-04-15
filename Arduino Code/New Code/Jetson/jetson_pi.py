import socket
import random
import time

# Host IP must match JETSON_IP in your hardware_logic.py
HOST = '192.168.1.100' 
# Port must match JETSON_PORT in your hardware_logic.py
PORT = 5005

# Sample soil types consistent with your dummy responses
SOIL_TYPES = ["Loam", "Clay", "Silt", "Sand"]

def start_server():
    # Create a TCP/IP socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        # Bind the socket to the address and port
        s.bind((HOST, PORT))
        # Listen for incoming connections
        s.listen()
        print(f"Jetson Soil Analysis Server online at {HOST}:{PORT}")
        print("Waiting for Raspberry Pi...")

        while True:
            # Wait for a connection from the Pi
            conn, addr = s.accept()
            with conn:
                print(f"Connected by {addr}")
                # Receive the command (e.g., "ANALYZE 0,0")
                data = conn.recv(1024).decode()
                
                if data.startswith("ANALYZE"):
                    print(f"Processing request: {data}")
                    
                    # Simulate computer vision processing time
                    time.sleep(1.5) 
                    
                    # Generate sample analysis data
                    result_type = random.choice(SOIL_TYPES)
                    
                    # For image data, you can send a URL or a local file path
                    # Your current logic handles both strings and URL seeds
                    mock_image = f"https://picsum.photos/seed/{random.random()}/400/300"
                    
                    # Format the response as "SoilType|ImageData"
                    response = f"{result_type}|{mock_image}"
                    
                    # Send the response back to the Pi
                    conn.sendall(response.encode())
                    print(f"Analysis complete. Sent: {response}")

if __name__ == "__main__":
    try:
        start_server()
    except KeyboardInterrupt:
        print("\nServer stopped by user.")