import os
import subprocess
import time
import paho.mqtt.client as mqtt
import base64
import requests
import hashlib
import uuid
import re
import requests
from threading import Thread

# Load configuration from environment variables
PROVISIONING_SERVICE_URL = os.environ.get("PROVISIONING_SERVICE_URL")
MQTT_BROKER = os.environ.get("MQTT_BROKER")
MQTT_PORT = int(os.environ.get("MQTT_PORT", 1883))
MQTT_TOPIC = os.environ.get("MQTT_TOPIC", "frames")
MQTT_BROKER_USERNAME = os.environ.get("MQTT_BROKER_USERNAME")
MQTT_BROKER_PASSWORD = os.environ.get("MQTT_BROKER_PASSWORD")
MQTT_REAUTH_TOPIC = os.environ.get("MQTT_REAUTH_TOPIC", "request-auth")
AUTH_SERVICE_URL = os.environ.get("AUTH_SERVICE_URL")
FRAMES_OUTPUT_DIRECTORY = "frames_captured"

mac_address = ""

# Function to calculate the SHA-256 hash of a file
def calculate_hash(file_path):
    """
    Calculate the SHA-256 hash of a file.

    Args:
        file_path (str): Path to the file.

    Returns:
        str: Hexadecimal representation of the calculated hash.
    """
    try:
        with open(file_path, "rb") as f:
            file_content = f.read()
            hash_object = hashlib.sha256(file_content)
            hash_hex = hash_object.hexdigest()
            return hash_hex
    except Exception as e:
        print("Error calculating hash:", e)
        return None

# Function to obtain the MAC address of the device
def get_mac_address():
    """
    Obtain the MAC address of the device.

    Returns:
        str: MAC address of the device.
    """
    try:
        output = subprocess.check_output(["ifconfig", "eth0"], stderr=subprocess.STDOUT, text=True)
        mac_address = re.search(r"(\w\w:\w\w:\w\w:\w\w:\w\w:\w\w)", output).group(0)
        return mac_address
    except Exception as e:
        print("Error obtaining MAC address:", e)
        return None

# Function to retrieve a challenge for authentication
def get_challenge(mac_address):
    """
    Retrieve a challenge for authentication.

    Args:
        mac_address (str): MAC address of the device.

    Returns:
        str: Authentication challenge.
    """
    try:
        response = requests.post(f"{AUTH_SERVICE_URL}/get_challenge", json={"mac_address": mac_address})
        if response.status_code == 200:
            data = response.json()
            return data.get("challenge")
        return None
    except Exception as e:
        print("Error getting challenge:", e)
        return None


# Function to authenticate using CHAP (Challenge-Handshake Authentication Protocol)
def authenticate_chap(mac_address, client_response):
    """
    Authenticate using CHAP (Challenge-Handshake Authentication Protocol).

    Args:
        mac_address (str): MAC address of the device.
        client_response (str): Client's response to the challenge.

    Returns:
        bool: True if authentication is successful, False otherwise.
    """
    try:
        response = requests.post(f"{AUTH_SERVICE_URL}/authenticate", json={"mac_address": mac_address, "client_response": client_response})
        if response.status_code == 200:
            return True
        return False
    except Exception as e:
        print("Error during authentication:", e)
        return False

# Callback function when the MQTT client connects to the broker
def on_connect(client, userdata, flags, rc):
    """
    Callback function when the MQTT client connects to the broker.

    Args:
        client: The MQTT client instance.
        userdata: User data.
        flags: Connection flags.
        rc: Result code.
    """
    if rc == 0:
        print("Connected to MQTT broker")
    else:
        print("Connection error with code:", rc)

# Callback function when an MQTT message is received
def on_message(client, userdata, message):
    """
    Callback function when an MQTT message is received.

    Args:
        client: The MQTT client instance.
        userdata: User data.
        message: The received message.
    """
    try:
        topic = message.topic
        payload = message.payload.decode("utf-8")
        if topic == "__keyevent@0__:expired" and mac_address in payload:
            print("Received session expiration notification. Re-authenticating...")
            authenticate(mac_address)
    except Exception as e:
        print("Error handling MQTT message:", e)

# Function to capture a frame, encode it in base64, and send it over MQTT
def capture_and_send_frame(frame_path, timestamp, camera_url, mac_address):
    """
    Capture a frame, encode it in base64, and send it over MQTT.

    Args:
        frame_path (str): Path to the captured frame.
        timestamp (str): Timestamp of the capture.
        camera_url (str): URL of the camera feed.
        mac_address (str): MAC address of the device.
    """
    try:
        capture_command = [
            "ffmpeg",
            "-rtsp_transport", "tcp",  # Use TCP for RTSP streaming
            "-i", camera_url,
            "-vf", "fps=1",  # Capture one frame per second
            "-frames:v", "1",  # capture only one frame
            "-f", "image2",
            frame_path
        ]
        subprocess.run(capture_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        with open(frame_path, "rb") as frame_file:
            frame_data = frame_file.read()
            base64_frame = base64.b64encode(frame_data).decode('utf-8')
            payload = {
                "mac_address": mac_address,
                "timestamp": timestamp,
                "frame_data": base64_frame
            }
            client.publish(MQTT_TOPIC, payload=str(payload), qos=0)
            print("Frame sent to MQTT")
        os.remove(frame_path)
    except Exception as e:
        print("Error:", e)

# Function for the frame capture loop
def frame_capture_loop(camera_url, mac_address):
    """
    Frame capture loop.

    Args:
        camera_url (str): URL of the camera feed.
        mac_address (str): MAC address of the device.
    """
    while True:
        timestamp = str(int(time.time()))
        frame_filename = f"frame_{timestamp}.jpg"
        frame_path = os.path.join("output_directory", frame_filename)
        capture_and_send_frame(frame_path, timestamp, camera_url, mac_address)
        time.sleep(1)

# Function to authenticate the device
def authenticate(mac_address):
    """
    Authenticate the device.

    Args:
        mac_address (str): MAC address of the device.

    Returns:
        bool: True if authentication is successful, False otherwise.
    """
    try:
        code_file_path = os.path.abspath(__file__)
        code_hash = calculate_hash(code_file_path)
        print("Hash value of this code:", code_hash)
        challenge = get_challenge(mac_address)
        if challenge:
            password_response = requests.get(f"{PROVISIONING_SERVICE_URL}/get-fog-password?mac_address={mac_address}")
            if password_response.status_code == 200:
                password_data = password_response.json()
                node_password = password_data.get("fog_password")
                if node_password:
                    client_response = hashlib.sha256((node_password + challenge + code_hash).encode()).hexdigest()
                    return authenticate_chap(mac_address, client_response)
                else:
                    print("Error retrieving node password from provisioning service")
            else:
                print("Error getting node password from provisioning service")
        else:
            print("Error getting challenge")
    except Exception as e:
        print("Error during reauthentication:", e)
        return False
    
# Initialize the MQTT client and set up callbacks
client = mqtt.Client()
client.username_pw_set(username=MQTT_BROKER_USERNAME, password=MQTT_BROKER_PASSWORD)
client.on_connect = on_connect
client.on_message = on_message
client.connect(MQTT_BROKER, MQTT_PORT, 60)
client.subscribe(MQTT_REAUTH_TOPIC)
client.loop_start()

# Main function
def main():
    """
    Main function.
    """
    global mac_address
    mac_address = get_mac_address()

    if mac_address is None:
        mac_address = str(uuid.uuid4())

    if not os.path.exists(FRAMES_OUTPUT_DIRECTORY):
        os.makedirs(FRAMES_OUTPUT_DIRECTORY)

    if authenticate(mac_address):
        try:
            response = requests.get(f"{PROVISIONING_SERVICE_URL}?mac_address={mac_address}")
            if response.status_code == 200:
                provisioning_data = response.json()
                camera_url = provisioning_data.get("camera_url")
                camera_username = provisioning_data.get("camera_username")
                camera_password = provisioning_data.get("camera_password")
                capture_thread = Thread(target=frame_capture_loop, args=(camera_url, camera_username, camera_password))
                capture_thread.start()
            else:
                print("Error retrieving provisioning data")
        except Exception as e:
            print("Error during provisioning:", e)
    else:
        print(f"Error authenticating fog node with MAC {mac_address}")

# Entry point of the script
if __name__ == "__main__":
    main()