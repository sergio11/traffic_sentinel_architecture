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
import redis

# Load configuration from environment variables
provisioning_service_url = os.environ.get("PROVISIONING_SERVICE_URL")
mqtt_broker = os.environ.get("MQTT_BROKER")
mqtt_port = int(os.environ.get("MQTT_PORT", 1883))
mqtt_topic = os.environ.get("MQTT_TOPIC", "frames")
mqtt_username = os.environ.get("MQTT_USERNAME")
mqtt_password = os.environ.get("MQTT_PASSWORD")
mqtt_ca_cert = os.environ.get("MQTT_CA_CERT")
auth_service_url = os.environ.get("AUTH_SERVICE_URL")
vault_address = os.environ.get("VAULT_ADDRESS", "http://vault:8200")
redis_host = os.environ.get("REDIS_HOST", "redis")
redis_port = int(os.environ.get("REDIS_PORT", 6379))
redis_client = redis.Redis(host=redis_host, port=redis_port, db=0)

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
        response = requests.post(f"{auth_service_url}/get_challenge", json={"mac_address": mac_address})
        if response.status_code == 200:
            data = response.json()
            return data.get("challenge")
        return None
    except Exception as e:
        print("Error getting challenge:", e)
        return None

# Function to retrieve the Vault token from Redis
def get_vault_token():
    """
    Retrieve the Vault token from Redis.

    Returns:
        str: Vault token.
    """
    try:
        token = redis_client.get("vault_root_token")
        if token:
            return token.decode("utf-8")
        else:
            raise Exception("Vault token not found in Redis")
    except Exception as e:
        raise Exception("Error retrieving Vault token from Redis")

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
        response = requests.post(f"{auth_service_url}/authenticate", json={"mac_address": mac_address, "client_response": client_response})
        if response.status_code == 200:
            return True
        return False
    except Exception as e:
        print("Error during authentication:", e)
        return False

# Function to retrieve the node password from Vault
def get_node_password(mac_address):
    """
    Retrieve the node password from Vault.

    Args:
        mac_address (str): MAC address of the device.

    Returns:
        str: Node password.
    """
    try:
        response = requests.get(
            f"{vault_address}/v1/secret/data/users/{mac_address}",
            headers={"X-Vault-Token": get_vault_token()}
        )
        response_json = response.json()
        node_password = response_json["data"]["password"]
        return node_password
    except Exception as e:
        print("Error retrieving node password from Vault:", e)
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
            client.publish(mqtt_topic, payload=str(payload), qos=0)
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
            node_password = get_node_password(mac_address)
            if node_password:
                client_response = hashlib.sha256((node_password + challenge + code_hash).encode()).hexdigest()
                return authenticate_chap(mac_address, client_response)
            else:
                print("Error retrieving node password from Vault")
        else:
            print("Error getting challenge")
    except Exception as e:
        print("Error during reauthentication:", e)
        return False

# Initialize the MQTT client and set up callbacks
client = mqtt.Client()
client.username_pw_set(username=mqtt_username, password=mqtt_password)
client.tls_set(ca_certs=mqtt_ca_cert)
client.on_connect = on_connect
client.on_message = on_message
client.connect(mqtt_broker, mqtt_port, 60)
client.subscribe("__keyevent@0__:expired")
client.loop_start()

# Main function
def main():
    """
    Main function.
    """
    mac_address = get_mac_address()

    if mac_address is None:
        mac_address = str(uuid.uuid4())

    if not os.path.exists("output_directory"):
        os.makedirs("output_directory")

    if authenticate(mac_address):
        try:
            response = requests.get(f"{provisioning_service_url}?mac_address={mac_address}")
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
