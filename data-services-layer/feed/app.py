import threading
from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit
from confluent_kafka import Consumer, KafkaError
import re

app = Flask(__name__)
socketio = SocketIO(app)

# Kafka Configuration
KAFKA_TOPIC = "frames"
KAFKA_GROUP_ID = "frame_stream"

# Class to manage client connections
class FrameStreamNamespace:
    def __init__(self):
        self.clients = set()
        self.mac_address = None

    def on_connect(self):
        self.clients.add(request.sid)
        print(f"Client {request.sid} connected")

    def on_disconnect(self):
        self.clients.remove(request.sid)
        print(f"Client {request.sid} disconnected")

# Function to consume Kafka events and emit them to clients
def consume_kafka_messages():
    c = Consumer({
        'bootstrap.servers': 'localhost:9092',  # Change this based on your Kafka configuration
        'group.id': KAFKA_GROUP_ID,
        'auto.offset.reset': 'earliest'
    })
    c.subscribe([KAFKA_TOPIC])

    while True:
        msg = c.poll(1.0)
        if msg is None:
            continue
        if msg.error():
            if msg.error().code() == KafkaError._PARTITION_EOF:
                continue
            else:
                print(f"Kafka Error: {msg.error().str()}")
                break
        else:
            frame_data = msg.value().decode('utf-8')
            if frame_stream_namespace.mac_address:
                # Emit Kafka message to all connected clients in the namespace
                socketio.emit('new_frame', frame_data, namespace='/frame_stream', room=frame_stream_namespace.mac_address)

# Initialize the namespace for managing client connections
frame_stream_namespace = FrameStreamNamespace()

# Route for clients to register for a specific MAC address
@app.route('/register/<mac_address>', methods=['POST'])
def register(mac_address):
    # Validate if the MAC address is valid
    if _is_valid_mac_address(mac_address):
        frame_stream_namespace.mac_address = mac_address
        return jsonify(message=f"Registered for MAC address {mac_address}")
    else:
        return jsonify(message="Invalid MAC address"), 400

def _is_valid_mac_address(mac_address):
    # Define a regular expression pattern for a MAC address in the form "00:1A:2B:3C:4D:5E"
    pattern = re.compile(r'^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$')
    return bool(pattern.match(mac_address))

if __name__ == '__main__':
    # Start consuming Kafka events
    kafka_thread = threading.Thread(target=consume_kafka_messages)
    kafka_thread.daemon = True
    kafka_thread.start()

    socketio.on_namespace(frame_stream_namespace)
    socketio.run(app, debug=True, use_reloader=False)