import os
import subprocess
import time
import paho.mqtt.client as mqtt
import base64
import requests
import hashlib
import uuid
import re
from threading import Thread
import redis

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

def calculate_hash(file_path):
    try:
        with open(file_path, "rb") as f:
            file_content = f.read()
            hash_object = hashlib.sha256(file_content)
            hash_hex = hash_object.hexdigest()
            return hash_hex
    except Exception as e:
        print("Error calculating hash:", e)
        return None


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
    
def get_vault_token():
    try:
        token = redis_client.get("vault_root_token")
        if token:
            return token.decode("utf-8")
        else:
            raise Exception("Vault token not found in Redis")
    except Exception as e:
        raise Exception("Error retrieving Vault token from Redis")

def authenticate_chap(mac_address, client_response):
    try:
        response = requests.post(f"{auth_service_url}/authenticate", json={"mac_address": mac_address, "client_response": client_response})
        if response.status_code == 200:
            return True
        return False
    except Exception as e:
        print("Error during authentication:", e)
        return False

def get_node_password(mac_address):
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

    code_file_path = os.path.abspath(__file__)
    code_hash = calculate_hash(code_file_path)

    print("Hash value of this code:", code_hash)

    if not os.path.exists("output_directory"):
        os.makedirs("output_directory")

    challenge = get_challenge(mac_address)

    if challenge:
        node_password = get_node_password(mac_address)
        if node_password:
            client_response = hashlib.sha256((node_password + challenge + code_hash).encode()).hexdigest()
            if authenticate_chap(mac_address, client_response):
                capture_thread = Thread(target=frame_capture_loop)
                capture_thread.start()
            else:
                print("Unauthorized node")
        else:
            print("Error retrieving node password from Vault")
    else:
        print("Error getting challenge")

if __name__ == "__main__":
    main()