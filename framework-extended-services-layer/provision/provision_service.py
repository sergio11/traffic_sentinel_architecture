from flask import Flask, request, jsonify
from redis
from pymongo import MongoClient
import os
import requests

app = Flask(__name__)

# Redis Configuration
REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
REDIS_PORT = int(os.environ.get("REDIS_PORT", 6379))
redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT);

VAULT_ADDRESS = os.environ.get("VAULT_ADDRESS", "http://vault:8200")
# MongoDB Configuration
MONGO_HOST = os.environ.get("MONGO_HOST", "localhost")
MONGO_PORT = int(os.environ.get("MONGO_PORT", 27017))
mongo_client = MongoClient(f"mongodb://{MONGO_PORT}:{MONGO_HOST}/")
db = mongo_client["camera_db"]

@app.route("/get-fog-password", methods=["GET"])
def get_fog_password():
    mac_address = request.args.get("mac_address")
    if mac_address:
        node_password = _get_node_password(mac_address)
        if node_password:
            return jsonify({"fog_password": node_password}), 200
        else:
            return jsonify({"message": "Node password not found"}), 404
    else:
        return jsonify({"message": "MAC address not provided"}), 400

# Endpoint to provision a camera by MAC address
@app.route("/provision", methods=["GET"])
def provision_camera():
    mac_address = request.args.get("mac_address")

    if mac_address:
        camera_info = db.cameras.find_one({"mac_address": mac_address})

        if camera_info:
            camera_url = camera_info.get("camera_url")
            camera_username = camera_info.get("camera_username")
            camera_password = camera_info.get("camera_password")

            session_id = request.headers.get("X-Session-ID")
            if session_id:
                if redis_client.exists(session_id):
                    # Remove the session key after successful provisioning
                    redis_client.delete(session_id)
                    response = {
                        "camera_url": camera_url,
                        "camera_username": camera_username,
                        "camera_password": camera_password,
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


@app.route("/provision/link", methods=["POST"])
def provision_camera():
    data = request.get_json()

    mac_address = data.get("mac_address")
    camera_url = data.get("camera_url")
    camera_username = data.get("camera_username")
    camera_password = data.get("camera_password")

    if not mac_address or not camera_url or not camera_username or not camera_password:
        return jsonify(message="Missing required data"), 400

    existing_camera = db.cameras.find_one({"mac_address": mac_address})
    if existing_camera:
        return jsonify(message="MAC address already exists"), 409

    db.cameras.insert_one(
        {
            "mac_address": mac_address,
            "camera_url": camera_url,
            "camera_username": camera_username,
            "camera_password": camera_password,
        }
    )

    return jsonify(message="Camera provisioned successfully"), 201


# Endpoint to remove the association of a camera with a MAC address
@app.route("/provision/remove", methods=["DELETE"])
def remove_camera_association():
    mac_address = request.args.get("mac_address")

    if mac_address:
        camera_info = db.cameras.find_one({"mac_address": mac_address})

        if camera_info:
            db.cameras.delete_one({"mac_address": mac_address})
            return jsonify(message="Camera association removed"), 200
        else:
            return jsonify(message="MAC address not found in database"), 404
    else:
        return jsonify(message="MAC address not provided"), 400


# Endpoint to retrieve the complete list of MACs with their associated cameras
@app.route("/provision/list", methods=["GET"])
def get_camera_associations():
    camera_associations = []

    cursor = db.cameras.find({})
    for camera_info in cursor:
        camera_associations.append(
            {
                "mac_address": camera_info.get("mac_address"),
                "camera_url": camera_info.get("camera_url"),
                "camera_username": camera_info.get("camera_username"),
                "camera_password": camera_info.get("camera_password"),
            }
        )

    return jsonify(camera_associations), 200

# Function to retrieve the Vault token from Redis
def _get_vault_token():
    """
    Retrieve the Vault token from Redis.

    Returns:
        str: Vault token.
    """
    try:
        token = redis_client.get("vault_root_token")
        if token:
            return token.decode("utf-8")
        else:
            raise Exception("Vault token not found in Redis")
    except Exception as e:
        raise Exception("Error retrieving Vault token from Redis")
    
# Function to retrieve the node password from Vault
def _get_node_password(mac_address):
    """
    Retrieve the node password from Vault.

    Args:
        mac_address (str): MAC address of the device.

    Returns:
        str: Node password.
    """
    try:
        response = requests.get(
            f"{VAULT_ADDRESS}/v1/secret/data/users/{mac_address}",
            headers={"X-Vault-Token": _get_vault_token()}
        )
        response_json = response.json()
        node_password = response_json["data"]["password"]
        return node_password
    except Exception as e:
        print("Error retrieving node password from Vault:", e)
        return None

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)
