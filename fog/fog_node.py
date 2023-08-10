import os
import subprocess
import time
import paho.mqtt.client as mqtt
import base64
import requests
import hashlib
import uuid
from threading import Thread
import re
import hvac

# Retrieve configuration from environment variables
auth_service_url = os.environ.get("AUTH_SERVICE_URL")
mqtt_broker = os.environ.get("MQTT_BROKER")
mqtt_port = int(os.environ.get("MQTT_PORT"))
mqtt_topic = os.environ.get("MQTT_TOPIC")
camera_url = os.environ.get("CAMERA_URL")
output_directory = os.environ.get("OUTPUT_DIRECTORY")
vault_url = os.environ.get("VAULT_URL")
vault_token = os.environ.get("VAULT_TOKEN")
vault_secret_path = os.environ.get("VAULT_SECRET_PATH")
vault_field_name = os.environ.get("VAULT_FIELD_NAME")

def get_mac_address():
    try:
        output = subprocess.check_output(["ifconfig", "eth0"], stderr=subprocess.STDOUT, text=True)
        mac_address = re.search(r"(\w\w:\w\w:\w\w:\w\w:\w\w:\w\w)", output).group(0)
        return mac_address
    except Exception as e:
        print("Error obtaining MAC address:", e)
        return None

def authenticate_chap(mac, password):
    try:
        challenge_response = requests.post(auth_service_url, json={"mac_address": mac})
        if challenge_response.status_code == 200:
            challenge = challenge_response.json().get("challenge")
            response = hashlib.sha256((password + challenge).encode()).hexdigest()
            auth_response = requests.post(auth_service_url, json={"mac_address": mac, "client_response": response})
            if auth_response.status_code == 200:
                return True
        return False
    except Exception as e:
        print("Error during authentication:", e)
        return False

mac_address = get_mac_address()

if mac_address is None:
    mac_address = str(uuid.uuid4())

def get_vault_secret(secret_path, field_name):
    client = hvac.Client(url=vault_url, token=vault_token)
    if client.is_authenticated():
        response = client.read(secret_path)
        if response and 'data' in response and field_name in response['data']:
            return response['data'][field_name]
    return None

node_password = get_vault_secret(vault_secret_path, vault_field_name)

if node_password is None:
    print("Failed to retrieve password from Vault")
    exit(1)

client = mqtt.Client()

client.username_pw_set(username=os.environ.get("MQTT_USERNAME"), password=os.environ.get("MQTT_PASSWORD"))
client.tls_set(ca_certs=os.environ.get("MQTT_CA_CERT"))

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("Connected to MQTT broker")
    else:
        print("Connection error with code:", rc)

client.on_connect = on_connect

client.connect(mqtt_broker, mqtt_port, 60)

def capture_and_send_frame(frame_path):
    try:
        subprocess.run(["ffmpeg", "-i", camera_url, "-vframes", "1", frame_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        with open(frame_path, "rb") as frame_file:
            frame_data = frame_file.read()
            base64_frame = base64.b64encode(frame_data).decode('utf-8')
            timestamp = int(time.time())
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

def frame_capture_loop():
    while True:
        timestamp = str(int(time.time()))
        frame_filename = f"frame_{timestamp}.jpg"
        frame_path = os.path.join(output_directory, frame_filename)
        capture_and_send_frame(frame_path)
        time.sleep(1)

def main():
    if not os.path.exists(output_directory):
        os.makedirs(output_directory)

    if authenticate_chap(mac_address, node_password):
        capture_thread = Thread(target=frame_capture_loop)
        capture_thread.start()
    else:
        print("Unauthorized node")

if __name__ == "__main__":
    main()
