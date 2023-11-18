import logging
import os
import threading
from flask import request
from confluent_kafka import Consumer, KafkaError
from flask_socketio import Namespace, join_room, leave_room

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
        self.kafka_thread = None

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
            # Unsubscribe from camera before disconnecting
            self.unsubscribe_from_camera(client_sid)
            del self.clients[client_sid]
            logger.info(f"Client {client_sid} disconnected")

    def subscribe_to_camera(self, client_sid, camera_id):
        """
        Subscribes a client to a specific camera.

        Parameters:
        - client_sid: Session ID of the client.
        - camera_id: ID of the camera to subscribe to.
        """
        if client_sid in self.clients:
            if self.clients[client_sid] != camera_id:
                # Unsubscribe from previous camera room if already subscribed
                self.unsubscribe_from_camera(client_sid)

            self.clients[client_sid] = camera_id
            join_room(camera_id)
            logger.info(f"Client {client_sid} subscribed to camera {camera_id}")
            logger.info(f"Check Clients and start kafka consumer")
            self._check_clients_and_start_kafka_consumer()

    def unsubscribe_from_camera(self, client_sid):
        """
        Unsubscribes a client from a camera.

        Parameters:
        - client_sid: Session ID of the client.
        """
        if client_sid in self.clients:
            camera_id = self.clients[client_sid]
            leave_room(camera_id)
            self.clients[client_sid] = None
            logger.info(f"Client {client_sid} unsubscribed from camera {camera_id}")
        else:
            logger.info(f"Client {client_sid} is not subscribed to any camera")

    def _check_clients_and_start_kafka_consumer(self):
        logger.info("_check_clients_and_start_kafka_consumer ...")
        if len(self.clients) > 0 and self.kafka_thread is None:
            self.kafka_thread = threading.Thread(target=self._start_kafka_consumer)
            self.kafka_thread.start()
            logger.info("Started Kafka consumer thread because there are connected clients")
        elif len(self.clients) == 0 and self.kafka_thread is not None:
            self.kafka_thread = None
            logger.info("Stopped Kafka consumer thread because there are no connected clients")
        elif len(self.clients) > 0 and self.kafka_thread is not None:
            logger.info("Kafka consumer thread is already running and there are connected clients")
        else:
            logger.info("No action taken as there are no connected clients and Kafka consumer thread is not running")

    def _start_kafka_consumer(self):
        """
        Consumes Kafka messages and emits them to clients subscribed to the respective cameras.
        """
        c = Consumer({
            'bootstrap.servers': KAFKA_BOOTSTRAP_SERVERS,
            'group.id': KAFKA_GROUP_ID,
            'auto.offset.reset': 'earliest'
        })
        c.subscribe([KAFKA_TOPIC])

        logger.info("Kafka consumer started")

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
                logger.info(f"Received message from Kafka: {frame_data}")
                for client_sid, camera_id in self.clients.items():
                    if camera_id and camera_id == msg.camera_id:
                        self.emit('new_frame', frame_data, namespace='/traffic_sentinel_stream', room=client_sid)
                        logger.info(f"Emitted new_frame event to client {client_sid} for camera {camera_id}")  # Log de emisión del mensaje a clientes

        c.close()
        logger.info("Kafka consumer stopped")