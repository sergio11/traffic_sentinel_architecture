import json
import os
import threading
from confluent_kafka import Consumer, KafkaError
from flask_socketio import Namespace, join_room, leave_room


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
    def __init__(self, logger):
        """
        Initializes the ClientManager.
        """
        super().__init__(namespace='/traffic_sentinel_stream')
        self.clients = {}
        self.kafka_thread = None
        self.logger = logger

    def on_connect(self, client_sid):
        """
        Handles a new client connection and adds it to the clients dictionary.
        """
        self.clients[client_sid] = None  # Initially, the client is not subscribed to any camera
        self.logger.info(f"Client {client_sid} connected")

    
    def on_disconnect(self, client_sid):
        """
        Handles a client disconnection and removes it from the clients dictionary.
        """
        if client_sid in self.clients:
            # Unsubscribe from camera before disconnecting
            self.unsubscribe_from_camera(client_sid)
            del self.clients[client_sid]
            self.logger.info(f"Client {client_sid} disconnected")
            

    def subscribe_to_camera(self, client_sid, camera_id):
        """
        Subscribes a client to a specific camera.

        Parameters:
        - client_sid: Session ID of the client.
        - camera_id: ID of the camera to subscribe to.
        """
        if client_sid in self.clients:
            if self.clients[client_sid] is not None and self.clients[client_sid] != camera_id:
                # Unsubscribe from previous camera room if already subscribed
                self.unsubscribe_from_camera(client_sid)

            self.clients[client_sid] = camera_id
            join_room(camera_id)
            self.logger.info(f"Client {client_sid} subscribed to camera {camera_id}")
            self.logger.info(f"Check Clients and start kafka consumer")
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
            self.logger.info(f"Client {client_sid} unsubscribed from camera {camera_id}")
        else:
            self.logger.info(f"Client {client_sid} is not subscribed to any camera")

    def _check_clients_and_start_kafka_consumer(self):
        if len(self.clients) > 0 and self.kafka_thread is None:
            self.kafka_thread = threading.Thread(target=self._start_kafka_consumer)
            self.kafka_thread.start()
            self.logger.info("Started Kafka consumer thread because there are connected clients")
        elif len(self.clients) == 0 and self.kafka_thread is not None:
            self.kafka_thread = None
            self.logger.info("Stopped Kafka consumer thread because there are no connected clients")
        elif len(self.clients) > 0 and self.kafka_thread is not None:
            self.logger.info("Kafka consumer thread is already running and there are connected clients")
        else:
            self.logger.info("No action taken as there are no connected clients and Kafka consumer thread is not running")

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

        self.logger.info("Kafka consumer started")

        while True:
            msg = c.poll(1.0)
            if msg is None:
                continue
            if msg.error():
                if msg.error().code() == KafkaError._PARTITION_EOF:
                    continue
                else:
                    self.logger.info(f"Kafka Error: {msg.error().str()}")
                    break
            else:
                frame_data = msg.value().decode('utf-8')
                payload = json.loads(frame_data) 
                camera_id = payload.get('camera_id')
                self.logger.info(f"Received new message from Kafka with camera id: {camera_id}")

                for client_sid, subscribed_camera_id in self.clients.items():
                    if subscribed_camera_id and subscribed_camera_id == camera_id:
                        self.emit('new_frame', frame_data, namespace='/traffic_sentinel_stream', room=client_sid)
                        self.logger.info(f"Emitted new_frame event to client {client_sid} for camera {camera_id}")

        c.close()
        self.logger.info("Kafka consumer stopped")