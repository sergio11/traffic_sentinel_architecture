import os
import subprocess
import time
import paho.mqtt.client as mqtt
import base64
import requests
import hashlib
import uuid
from threading import Thread

mqtt_broker = os.environ.get("MQTT_BROKER")
mqtt_port = int(os.environ.get("MQTT_PORT", 1883))
mqtt_topic = os.environ.get("MQTT_TOPIC", "frames")
mqtt_username = os.environ.get("MQTT_USERNAME")
mqtt_password = os.environ.get("MQTT_PASSWORD")
mqtt_ca_cert = os.environ.get("MQTT_CA_CERT")
auth_service_url = os.environ.get("AUTH_SERVICE_URL")
node_password = os.environ.get("NODE_PASSWORD")


def get_mac_address():
    try:
        output = subprocess.check_output(["ifconfig", "eth0"], stderr=subprocess.STDOUT, text=True)
        mac_address = re.search(r"(\w\w:\w\w:\w\w:\w\w:\w\w:\w\w)", output).group(0)
        return mac_address
    except Exception as e:
        print("Error obtaining MAC address:", e)
        return None

def get_challenge(mac_address):
    try:
        response = requests.post(f"{auth_service_url}/get_challenge", json={"mac_address": mac_address})
        if response.status_code == 200:
            data = response.json()
            return data.get("challenge")
        return None
    except Exception as e:
        print("Error getting challenge:", e)
        return None

def authenticate_chap(mac_address, client_response):
    try:
        response = requests.post(f"{auth_service_url}/authenticate", json={"mac_address": mac_address, "client_response": client_response})
        if response.status_code == 200:
            return True
        return False
    except Exception as e:
        print("Error during authentication:", e)
        return False

mac_address = get_mac_address()

if mac_address is None:
    mac_address = str(uuid.uuid4())

client = mqtt.Client()
client.username_pw_set(username=mqtt_username, password=mqtt_password)
client.tls_set(ca_certs=mqtt_ca_cert)

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("Connected to MQTT broker")
    else:
        print("Connection error with code:", rc)

client.on_connect = on_connect

client.connect(mqtt_broker, mqtt_port, 60)

def capture_and_send_frame(frame_path):
    try:
        subprocess.run(["ffmpeg", "-i", "camera_url", "-vframes", "1", frame_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
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
        frame_path = os.path.join("output_directory", frame_filename)
        capture_and_send_frame(frame_path)
        time.sleep(1)

def main():
    if not os.path.exists("output_directory"):
        os.makedirs("output_directory")

    challenge = get_challenge(mac_address)

    if challenge:
        client_response = hashlib.sha256((node_password + challenge).encode()).hexdigest()
        if authenticate_chap(mac_address, client_response):
            capture_thread = Thread(target=frame_capture_loop)
            capture_thread.start()
        else:
            print("Unauthorized node")
    else:
        print("Error getting challenge")

if __name__ == "__main__":
    main()
