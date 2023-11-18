from client_manager import ClientManager
from flask import Flask, request
from flask_socketio import SocketIO, emit
import os
import logging
from pymongo import MongoClient
from bson import ObjectId

# Event logging configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# MongoDB Configuration
MONGO_CONNECTION_URL = os.environ.get("MONGO_CONNECTION_URL", "mongodb://localhost:27017/")
MONGO_DB = os.environ.get("MONGO_DB", "smarthighwaynet")
mongo_client = MongoClient(MONGO_CONNECTION_URL)
db = mongo_client[MONGO_DB]

# Initialize the client manager
clientManager = ClientManager(logger)

# Initialize Flask app and SocketIO
app = Flask(__name__)
socketio = SocketIO(app)
socketio.on_namespace(clientManager)

# Socket event handlers

@socketio.on('connect')
def on_connect():
    # Method called when a client connects to the server
    client_sid = request.sid
    clientManager.on_connect(client_sid)
     
@socketio.on('disconnect')
def on_disconnect():
    # Method called when a client disconnects from the server
    client_sid = request.sid
    clientManager.on_disconnect(client_sid)

@socketio.on('subscribe_camera')
def subscribe_camera(data):
    # Method called when a client requests to subscribe to a camera
    client_sid = request.sid
    camera_id = data.get('camera_id')
    logger.info(f"Client {client_sid} tries to subscribe to camera {camera_id}")
    camera = db.cameras.find_one({'_id': ObjectId(camera_id)})
    if camera is not None:
        clientManager.subscribe_to_camera(client_sid, camera_id)
        emit('subscription_success', {'message': f"Subscribed to camera ID {camera_id}"})
        logger.info(f"Client {client_sid} subscribed to camera {camera_id}")
    else:
        emit('subscription_error', {'message': "Invalid camera ID"}, status=400)
        logger.error(f"Invalid camera ID subscription request from client {client_sid}")

@socketio.on('unsubscribe_camera')
def unsubscribe_camera(data):
    # Method called when a client requests to unsubscribe from a camera
    client_sid = request.sid
    camera_id = data.get('camera_id')
    logger.info(f"Client {client_sid} tries to unsubscribe from camera {camera_id}")
    clientManager.unsubscribe_from_camera(client_sid)
    emit('unsubscription_success', {'message': f"Unsubscribed from camera ID {camera_id}"})
    logger.info(f"Client {client_sid} unsubscribed from camera {camera_id}")

if __name__ == '__main__':
    # Server execution
    socketio.run(app, debug=True, use_reloader=False)