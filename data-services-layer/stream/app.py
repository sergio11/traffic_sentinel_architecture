from client_manager import ClientManager
from flask import Flask, jsonify, request
from flask_socketio import SocketIO
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

clientManager = None

# Route for clients to subscribe for a specific camera ID
@app.route('/subscribe/<camera_id>', methods=['POST'])
def subscribe(camera_id):
    client_sid = request.sid
    # Check if the camera ID exists in the MongoDB cameras collection
    camera = db.cameras.find_one({'_id': ObjectId(camera_id)})
    if camera is not None:
        clientManager.subscribe_to_camera(client_sid, camera_id)
        return jsonify(message=f"Subscribed to camera ID {camera_id}")
    else:
        return jsonify(message="Invalid camera ID"), 400

# Main function
def main():
    global clientManager
    # Initialize the namespace for managing client connections
    clientManager = ClientManager()
    socketio.on_namespace(clientManager)
    socketio.run(app, debug=True, use_reloader=False)

if __name__ == '__main__':
    main()