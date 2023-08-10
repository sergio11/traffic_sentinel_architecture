import os
import subprocess
import time
import paho.mqtt.client as mqtt
import base64
import uuid
import requests
from threading import Thread
import re

# Dirección del servicio de autenticación
auth_service_url = "http://auth_service_url/authenticate"

# Función para obtener la dirección MAC de la interfaz de red
def get_mac_address():
    try:
        output = subprocess.check_output(["ifconfig", "eth0"], stderr=subprocess.STDOUT, text=True)
        mac_address = re.search(r"(\w\w:\w\w:\w\w:\w\w:\w\w:\w\w)", output).group(0)
        return mac_address
    except Exception as e:
        print("Error al obtener la dirección MAC:", e)
        return None

# Función para autenticar la dirección MAC
def authenticate_mac(mac):
    try:
        response = requests.post(auth_service_url, json={"mac_address": mac})
        if response.status_code == 200 and response.json().get("authorized"):
            return True
        return False
    except Exception as e:
        print("Error al autenticar:", e)
        return False

# Configuración de MQTT
mqtt_broker = "broker.example.com"
mqtt_port = 8883  # Puerto seguro TLS/SSL
mqtt_topic = "frames"

# Configuración de la cámara IP
camera_url = "rtsp://username:password@camera_ip_address:port/stream"

# Directorio para guardar los frames locales
output_directory = "frames/"

# Obtener la dirección MAC del host
mac_address = get_mac_address()

if mac_address is None:
    mac_address = str(uuid.uuid4())  # Generar un identificador único

# Inicialización del cliente MQTT
client = mqtt.Client()

# Configuración de autenticación y certificados
client.username_pw_set(username="tu_usuario", password="tu_contraseña")
client.tls_set(ca_certs="ruta_al_certificado_ca.crt")

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("Connecting to MQTT broker")
    else:
        print("An error ocurred when trying to connect to the MQTT broker:", rc)

client.on_connect = on_connect

client.connect(mqtt_broker, mqtt_port, 60)

# Función para capturar y enviar frames
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
        os.remove(frame_path)  # Elimina el frame del directorio local
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

    if authenticate_mac(mac_address):
        capture_thread = Thread(target=frame_capture_loop)
        capture_thread.start()
    else:
        print("Authorization has failed")

if __name__ == "__main__":
    main()
