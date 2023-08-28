from flask import Flask, request, jsonify
import redis
from pymongo import MongoClient
import os

app = Flask(__name__)

# Redis Configuration
REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
REDIS_PORT = int(os.environ.get("REDIS_PORT", 6379))
redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT)

# MongoDB Configuration
MONGO_HOST = os.environ.get("MONGO_HOST", "localhost")
MONGO_PORT = int(os.environ.get("MONGO_PORT", 27017))
mongo_client = MongoClient(f'mongodb://{MONGO_HOST}:{MONGO_PORT}/')
db = mongo_client['camera_db']

@app.route('/provision', methods=['GET'])
def provision_camera():
    mac_address = request.args.get('mac_address')

    if mac_address:
        camera_info = db.cameras.find_one({"mac_address": mac_address})

        if camera_info:
            camera_url = camera_info.get("camera_url")
            camera_username = camera_info.get("camera_username")
            camera_password = camera_info.get("camera_password")

            session_id = request.headers.get('X-Session-ID')
            if session_id:
                if redis_client.exists(session_id):
                    # Remove the session key after successful provisioning
                    redis_client.delete(session_id)
                    response = {
                        "camera_url": camera_url,
                        "camera_username": camera_username,
                        "camera_password": camera_password
                    }
                    return jsonify(response), 200
                else:
                    return jsonify(message="Invalid session ID"), 401
            else:
                return jsonify(message="Session ID not provided"), 400
        else:
            return jsonify(message="MAC address not found in database"), 404
    else:
        return jsonify(message="MAC address not provided"), 400

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001)
