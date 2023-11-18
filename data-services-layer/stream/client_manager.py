import logging
import os
import threading
from flask import request
from confluent_kafka import Consumer, KafkaError
from flask_socketio import Namespace

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load configuration from environment variables
KAFKA_BOOTSTRAP_SERVERS = os.environ.get('KAFKA_BROKER', 'localhost:9092')
KAFKA_GROUP_ID = os.environ.get('KAFKA_COMPLETED_GROUP_ID', 'default_group_id')
KAFKA_TOPIC = os.environ.get('KAFKA_COMPLETED_TOPIC', 'topic')

class ClientManager(Namespace):
    """
    Manages client connections and Kafka message consumption for camera subscriptions.

    Attributes:
    - clients (dict): A dictionary to store connected clients and their subscribed camera IDs.
    """
    def __init__(self):
        """
        Initializes the ClientManager.
        """
        super().__init__(namespace='/traffic_sentinel_stream')
        self.clients = {}

        # Start consuming Kafka events
        kafka_thread = threading.Thread(target=self._consume_kafka_messages)
        kafka_thread.daemon = True
        kafka_thread.start()

    def on_connect(self):
        """
        Handles a new client connection and adds it to the clients dictionary.
        """
        client_sid = request.sid
        self.clients[client_sid] = None  # Initially, the client is not subscribed to any camera
        logger.info(f"Client {client_sid} connected")

    def on_disconnect(self):
        """
        Handles a client disconnection and removes it from the clients dictionary.
        """
        client_sid = request.sid
        if client_sid in self.clients:
            del self.clients[client_sid]
            logger.info(f"Client {client_sid} disconnected")

    def subscribe_to_camera(self, client_sid, camera_id):
        """
        Subscribes a client to a specific camera.

        Parameters:
        - client_sid: Session ID of the client.
        - camera_id: ID of the camera to subscribe to.
        """
        self.clients[client_sid] = camera_id
        logger.info(f"Client {client_sid} subscribed to camera {camera_id}")

    def _consume_kafka_messages(self):
        """
        Consumes Kafka messages and emits them to clients subscribed to the respective cameras.
        """
        c = Consumer({
            'bootstrap.servers': KAFKA_BOOTSTRAP_SERVERS,
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
                    logger.info(f"Kafka Error: {msg.error().str()}")
                    break
            else:
                frame_data = msg.value().decode('utf-8')
                for client_sid, camera_id in self.clients.items():
                    if camera_id and camera_id == msg.camera_id:
                        self.emit('new_frame', frame_data, namespace='/traffic_sentinel_stream', room=client_sid)

        c.close()