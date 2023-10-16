import os
import subprocess
import time
import paho.mqtt.client as mqtt
import socket
import base64
import requests
import hashlib
import uuid
import re
import requests
from threading import Thread
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Load configuration from environment variables
PROVISIONING_SERVICE_URL = os.environ.get("PROVISIONING_SERVICE_URL", "http://localhost:5001/")
MQTT_BROKER = os.environ.get("MQTT_BROKER")
MQTT_PORT = int(os.environ.get("MQTT_PORT", 1883))
MQTT_TOPIC = os.environ.get("MQTT_TOPIC", "frames")
MQTT_BROKER_USERNAME = os.environ.get("MQTT_BROKER_USERNAME")
MQTT_BROKER_PASSWORD = os.environ.get("MQTT_BROKER_PASSWORD")
MQTT_REAUTH_TOPIC = os.environ.get("MQTT_REAUTH_TOPIC", "request-auth")
AUTH_SERVICE_URL = os.environ.get("AUTH_SERVICE_URL", "http://localhost:5000/")
FRAMES_OUTPUT_DIRECTORY = os.environ.get("FRAMES_OUTPUT_DIRECTORY", "frames_captured")
MAX_RETRIES = int(os.environ.get("MAX_RETRIES", 3))
RETRY_DELAY = int(os.environ.get("RETRY_DELAY", 10))

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
        logging.error("Error calculating hash: %s", e)
        return None

def get_host_ip():
    try:
        # Get the local host's IP address
        host_name = socket.gethostname()
        host_ip = socket.gethostbyname(host_name)
        return host_ip
    except Exception as e:
        print("Failed to obtain the IP address:", e)
        return None

def get_gps_info(ip):
    if ip:
        try:
            # Use the "ipinfo.io" geolocation service to retrieve GPS information
            url = f"https://ipinfo.io/{ip}/json"
            response = requests.get(url)
            data = response.json()
            return data
        except Exception as e:
            print("Failed to obtain GPS information:", e)
    return None

# Function to obtain the MAC address of the device
def get_mac_address():
    """
    Obtain the MAC address of the device.

    Returns:
        str: MAC address of the device.
    """
    try:
        output = subprocess.check_output(["ip", "link", "show", "eth0"], stderr=subprocess.STDOUT, text=True)
        mac_address = re.search(r"(\w\w:\w\w:\w\w:\w\w:\w\w:\w\w)", output).group(0)
        return mac_address
    except Exception as e:
        logging.error("Error obtaining MAC address: %s", e)
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
        else:
            logging.error("Failed to retrieve challenge. Status code: %d", response.status_code)
            return None
    except Exception as e:
        logging.error("Error getting challenge: %s", e)
        return None


# Function to authenticate using CHAP (Challenge-Handshake Authentication Protocol)
def authenticate_chap(mac_address, client_response):
    """
    Authenticate using CHAP (Challenge-Handshake Authentication Protocol).

    Args:
        mac_address (str): MAC address of the device.
        client_response (str): Client's response to the challenge.

    Returns:
        str: Session ID if authentication is successful, None otherwise.
    """
    try:
        global session_id  # Declare the global variable
        response = requests.post(f"{AUTH_SERVICE_URL}/authenticate", json={"mac_address": mac_address, "client_response": client_response})
        if response.status_code == 200:
            auth_data = response.json()
            session_id = auth_data.get("session_id")  # Retrieve the session_id from the response
            return session_id
        return None
    except Exception as e:
        logging.error("Error during authentication: %s", e)
        return None

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
        logging.info("Connected to MQTT broker")
    else:
        logging.error("Connection error with code: %s", rc)

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
            logging.info("Received session expiration notification. Re-authenticating...")
            authenticate(mac_address)
    except Exception as e:
        logging.error("Error handling MQTT message: %s", e)

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
    frame_path = os.path.join(FRAMES_OUTPUT_DIRECTORY, f"frame_{timestamp}.jpg")
    capture_command = [
        "ffmpeg",
        "-i", camera_url,
        "-vf", "fps=1",
        "-frames:v", "1",
        "-f", "image2",
        frame_path
    ]
    try:
        result = subprocess.run(capture_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if result.returncode == 0:
            if os.path.exists(frame_path):
                with open(frame_path, "rb") as frame_file:
                    frame_data = frame_file.read()
                    base64_frame = base64.b64encode(frame_data).decode('utf-8')
                    payload = {
                        "mac_address": mac_address,
                        "timestamp": timestamp,
                        "frame_data": base64_frame
                    }
                    client.publish(MQTT_TOPIC, payload=str(payload), qos=0)
                    logging.info("Frame sent to MQTT - MAC Address: %s, Timestamp: %s, Frame Size: %s bytes", mac_address, timestamp, len(base64_frame))
                    os.remove(frame_path)  # Remove the file after sending
            else:
                logging.error("The image file was not found at %s", frame_path)
        else:
            logging.error("Error capturing the image. ffmpeg output: %s", result.stderr)
    except Exception as e:
        logging.error("Error: %s", e)

# Function for the frame capture loop
def frame_capture_loop(mac_address, camera_url):
    """
    Frame capture loop.

    Args:
        mac_address (str): MAC address of the device.
        camera_url (str): URL of the camera feed.
    """
    while True:
        timestamp = str(int(time.time()))
        frame_filename = f"frame_{timestamp}.jpg"
        frame_path = os.path.join(FRAMES_OUTPUT_DIRECTORY, frame_filename)
        capture_and_send_frame(frame_path, timestamp, camera_url, mac_address)
        time.sleep(1)

# Function to authenticate the device
def authenticate(mac_address):
    """
    Authenticate the device.

    Args:
        mac_address (str): MAC address of the device.

    Returns:
        str: Session ID if authentication is successful, None otherwise.
    """
    try:
        code_file_path = os.path.abspath(__file__)
        code_hash = calculate_hash(code_file_path)
        logging.info("Hash value of this code: %s", code_hash)  # Log code hash

        challenge = get_challenge(mac_address)
        if challenge:
            password_response = requests.get(f"{PROVISIONING_SERVICE_URL}/get-fog-password?mac_address={mac_address}")
            if password_response.status_code == 200:
                password_data = password_response.json()
                node_password = password_data.get("fog_password")
                if node_password:
                    client_response = hashlib.sha256((node_password + challenge + code_hash).encode()).hexdigest()
                    session_id = authenticate_chap(mac_address, client_response)
                    if session_id:
                        logging.info("Device authenticated successfully with Session ID: %s", session_id)
                        return session_id
                    else:
                        logging.error("Authentication failed using CHAP")
                else:
                    logging.error("Error retrieving node password from provisioning service")
            else:
                logging.error("Error getting node password from provisioning service")
        else:
            logging.error("Error getting challenge")
    except Exception as e:
        logging.error("Error during reauthentication: %s", e)  # Log exception
        return None

    
# Function to authenticate the device with retries
def authenticate_with_retries(mac_address):
    """
    Authenticate the device with retries.

    Args:
        mac_address (str): MAC address of the device.

    Returns:
        str: Session ID if authentication is successful, None otherwise.
    """
    retries = 0
    while retries < MAX_RETRIES:
        session_id = authenticate(mac_address)
        if session_id:
            return session_id
        time.sleep(RETRY_DELAY)
        retries += 1
    return None

# Function to perform provisioning
def perform_provisioning(mac_address):
    session_id = authenticate_with_retries(mac_address)
    if session_id:
        return get_provisioning_data(session_id)
    else:
        logging.error("Error authenticating fog node with MAC %s", mac_address)
        return None

# Function to get provisioning data
def get_provisioning_data(session_id):
    headers = {
        "X-Session-Id": session_id
    }
    response = requests.get(f"{PROVISIONING_SERVICE_URL}/provision?mac_address={mac_address}", headers=headers)
    if response.status_code == 200:
        return response.json()
    else:
        logging.error(f"Error retrieving provisioning data. Status code: {response.status_code}")
        logging.error(f"Error response content: {response.text}")
        return None

# Function to start frame capture thread
def start_frame_capture(mac_address, full_camera_url):
    capture_thread = Thread(target=frame_capture_loop, args=(mac_address, full_camera_url))
    capture_thread.start()

# Function to send GPS information
def send_gps_information():
    ip = get_host_ip()
    if ip:
        print(f"Host's IP address: {ip}")
        gps_info = get_gps_info(ip)
        if gps_info:
            print("GPS Information:")
            print(f"Location: {gps_info.get('city')}, {gps_info.get('region')}, {gps_info.get('country')}")
            print(f"Latitude/Longitude: {gps_info.get('loc')}")
            # Send GPS information to the /update-gps-info endpoint
            response = requests.post(f"{PROVISIONING_SERVICE_URL}/update-gps-info", json={"mac_address": mac_address, "gps_info": gps_info})
            if response.status_code == 200:
                logging.info("GPS information sent successfully.")
            else:
                logging.error(f"Error sending GPS information. Status code: {response.status_code}")
        else:
            print("Failed to obtain GPS information.")
    else:
        print("Failed to obtain the host's IP address")

    
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
    global mac_address
    mac_address = get_mac_address()

    if mac_address is None:
        mac_address = str(uuid.uuid4())

    if not os.path.exists(FRAMES_OUTPUT_DIRECTORY):
        os.makedirs(FRAMES_OUTPUT_DIRECTORY)

    provisioning_data = perform_provisioning(mac_address)
    if provisioning_data:
        camera_url = provisioning_data.get("camera_url")
        camera_url_params = provisioning_data.get("camera_url_params")
        camera_username = provisioning_data.get("camera_username")
        camera_password = provisioning_data.get("camera_password")
        # Combine camera_url and camera_url_params
        full_camera_url = f"{camera_url}?{camera_url_params}"
        # Add username and password to the URL if available
        if camera_username and camera_password:
            credentials = f"{camera_username}:{camera_password}"
            base64_credentials = base64.b64encode(credentials.encode()).decode('utf-8')
            full_camera_url = f"{full_camera_url}@{base64_credentials}"
        start_frame_capture(mac_address, full_camera_url)
        send_gps_information()

# Entry point of the script
if __name__ == "__main__":
    main()
