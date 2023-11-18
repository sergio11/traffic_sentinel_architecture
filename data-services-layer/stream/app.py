from client_manager import ClientManager
from flask import Flask, request
from flask_socketio import SocketIO, emit
import os
import logging
from pymongo import MongoClient
from bson import ObjectId

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# MongoDB Configuration
MONGO_CONNECTION_URL = os.environ.get("MONGO_CONNECTION_URL", "mongodb://localhost:27017/")
MONGO_DB = os.environ.get("MONGO_DB", "db")
mongo_client = MongoClient(MONGO_CONNECTION_URL)
db = mongo_client[MONGO_DB]

app = Flask(__name__)
socketio = SocketIO(app)

# Initialize the namespace for managing client connections
clientManager = ClientManager()

@socketio.on('subscribe_camera')
def subscribe_camera(data):
    global clientManager
    client_sid = request.sid
    camera_id = data.get('camera_id')
    logger.info(f"Client {client_sid} try to subscribe to camera {camera_id}")
    camera = db.cameras.find_one({'_id': ObjectId(camera_id)})
    if camera is not None:
        clientManager.subscribe_to_camera(client_sid, camera_id)
        emit('subscription_success', {'message': f"Subscribed to camera ID {camera_id}"})
        logger.info(f"Client {client_sid} subscribed to camera {camera_id}")
    else:
        emit('subscription_error', {'message': "Invalid camera ID"}, status=400)
        logger.error(f"Invalid camera ID subscription request from client {client_sid}")

if __name__ == '__main__':
    socketio.on_namespace(clientManager)
    socketio.run(app, debug=True, use_reloader=False)