"""
Fog Notifier

This program listens to session expiration events in Redis and sends MQTT messages
to notify Fog nodes when their authentication sessions have expired. It subscribes
to the "__keyevent@0__:expired" channel in Redis, which emits messages when keys
with an expiration time set in Redis have expired.

When a session expires, the program extracts the MAC address from the key and sends
an MQTT message to the topic "reauth" to trigger the re-authentication process for
the corresponding Fog node.

Environment Variables:
- REDIS_HOST: Redis server hostname (default: localhost)
- REDIS_PORT: Redis server port (default: 6379)
- MQTT_BROKER: MQTT broker hostname (default: mqtt:1883)
- MQTT_PORT: MQTT broker port (default: 1883)
"""
import logging
import redis
import paho.mqtt.client as mqtt
import threading
import os
import time

REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
REDIS_PORT = int(os.environ.get("REDIS_PORT", 6379))
REDIS_EXPIRATION_CHANNEL = os.environ.get("REDIS_EXPIRATION_CHANNEL", "__keyevent@0__:expired") 
MQTT_BROKER = os.environ.get("MQTT_BROKER", "mqtt")
MQTT_PORT = int(os.environ.get("MQTT_PORT", 1883))
MQTT_REAUTH_TOPIC = os.environ.get("MQTT_REAUTH_TOPIC", "request-auth")

logging.basicConfig(level=logging.DEBUG)

# Connect to Redis
redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0)

# Connect to MQTT broker
mqtt_client = mqtt.Client()

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        logging.debug("Connected to MQTT broker")
    else:
        logging.debug("Connection error with code:", rc)

def on_message(client, userdata, message):
    if REDIS_EXPIRATION_CHANNEL in message.topic:
        # Extract the MAC address from the expired session key
        mac_address = message.payload.decode("utf-8").split("_")[0]

        # Send MQTT message to initiate authentication
        mqtt_client.publish(MQTT_REAUTH_TOPIC, mac_address)
        logging.debug(f"Sent MQTT message to restart authentication for MAC {mac_address}")

# Set MQTT callbacks
mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message

# Connect to MQTT broker
mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
mqtt_client.loop_start()

# Function to listen for Redis session expiration events
def listen_for_redis_events():
    redis_pubsub = redis_client.pubsub()
    redis_pubsub.psubscribe(REDIS_EXPIRATION_CHANNEL)
    
    logging.debug("Listening for session expiration events...")
    
    for message in redis_pubsub.listen():
        if message['type'] == 'pmessage':
            # Extract the MAC address from the expired session key
            mac_address = message['data'].decode("utf-8").split("_")[0]

            # Send MQTT message to initiate authentication
            mqtt_client.publish(MQTT_REAUTH_TOPIC, mac_address)
            logging.debug(f"Sent MQTT message to restart authentication for MAC {mac_address}")


# Start the Redis event listener thread
redis_thread = threading.Thread(target=listen_for_redis_events)
redis_thread.start()

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    logging.debug("Exiting...")
    redis_thread.join()  # Wait for the Redis thread to finish
    mqtt_client.loop_stop()
