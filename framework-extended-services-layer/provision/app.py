import logging
from flask import Flask, request, jsonify
import redis
from pymongo import MongoClient
import os
import hvac

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Redis Configuration
REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
REDIS_PORT = int(os.environ.get("REDIS_PORT", 6379))
redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT)

VAULT_ADDRESS = os.environ.get("VAULT_ADDRESS", "http://vault:8200")
# MongoDB Configuration
MONGO_HOST = os.environ.get("MONGO_HOST", "localhost")
MONGO_PORT = int(os.environ.get("MONGO_PORT", 27017))
mongo_client = MongoClient(f"mongodb://{MONGO_HOST}:{MONGO_PORT}/")
db = mongo_client["camera_db"]

@app.route("/get-fog-password", methods=["GET"])
def get_fog_password():
    logger.info("Received GET request for get_fog_password")
    
    # Get MAC address from the request's query parameters
    mac_address = request.args.get("mac_address")
    
    if mac_address:
        logger.debug(f"MAC address provided: {mac_address}")
        # Call the _get_node_password function to retrieve the node password
        node_password = _get_stored_password(mac_address)
        
        if node_password:
            logger.info(f"Node password retrieved for MAC {mac_address}")
            # Return the node password as JSON response
            return jsonify({"fog_password": node_password}), 200
        else:
            logger.warning("Node password not found")
            # Return a 404 response if node password is not found
            return jsonify({"message": "Node password not found"}), 404
    else:
        logger.error("MAC address not provided in request")
        # Return a 400 response if MAC address is not provided
        return jsonify({"message": "MAC address not provided"}), 400

@app.route("/provision", methods=["GET"])
def provision_camera():
    logger.info("Received GET request for provision_camera")
    
    # Get MAC address from the request's query parameters
    mac_address = request.args.get("mac_address")

    if mac_address:
        logger.debug(f"MAC address provided: {mac_address}")
        # Retrieve camera information from the MongoDB database
        camera_info = db.cameras.find_one({"mac_address": mac_address})

        if camera_info:
            logger.info(f"Camera info found for MAC {mac_address}")
            # Extract camera details
            camera_url = camera_info.get("camera_url")
            camera_username = camera_info.get("camera_username")
            camera_password = camera_info.get("camera_password")

            # Check the X-Session-ID header for authentication
            session_id = request.headers.get("X-Session-ID")
            if session_id:
                logger.debug(f"Session ID provided: {session_id}")
                if redis_client.exists(session_id):
                    logger.info(f"Session ID {session_id} exists in Redis")
                    # Remove the session key after successful provisioning
                    redis_client.delete(session_id)
                    response = {
                        "camera_url": camera_url,
                        "camera_username": camera_username,
                        "camera_password": camera_password,
                    }
                    return jsonify(response), 200
                else:
                    logger.warning("Invalid session ID")
                    return jsonify(message="Invalid session ID"), 401
            else:
                logger.error("Session ID not provided")
                return jsonify(message="Session ID not provided"), 400
        else:
            logger.warning(f"MAC address {mac_address} not found in database")
            return jsonify(message="MAC address not found in database"), 404
    else:
        logger.error("MAC address not provided in request")
        return jsonify(message="MAC address not provided"), 400

@app.route("/provision/link", methods=["POST"])
def provision_camera_link():
    logger.info("Received POST request for provision_camera_link")
    
    # Get JSON data from the request's body
    data = request.get_json()

    mac_address = data.get("mac_address")
    camera_url = data.get("camera_url")
    camera_username = data.get("camera_username")
    camera_password = data.get("camera_password")

    if not mac_address or not camera_url or not camera_username or not camera_password:
        logger.error("Missing required data in request body")
        return jsonify(message="Missing required data"), 400

    existing_camera = db.cameras.find_one({"mac_address": mac_address})
    if existing_camera:
        logger.warning("MAC address already exists in the database")
        return jsonify(message="MAC address already exists"), 409

    # Insert camera information into the MongoDB database
    db.cameras.insert_one(
        {
            "mac_address": mac_address,
            "camera_url": camera_url,
            "camera_username": camera_username,
            "camera_password": camera_password,
        }
    )

    logger.info(f"Camera provisioned successfully for MAC {mac_address}")
    return jsonify(message="Camera provisioned successfully"), 201

@app.route("/provision/remove", methods=["DELETE"])
def remove_camera_association():
    logger.info("Received DELETE request for remove_camera_association")
    
    # Get MAC address from the request's query parameters
    mac_address = request.args.get("mac_address")

    if mac_address:
        logger.debug(f"MAC address provided: {mac_address}")
        # Check if the MAC address exists in the MongoDB database
        camera_info = db.cameras.find_one({"mac_address": mac_address})

        if camera_info:
            # Delete the camera association from the MongoDB database
            db.cameras.delete_one({"mac_address": mac_address})
            logger.info(f"Camera association removed for MAC {mac_address}")
            return jsonify(message="Camera association removed"), 200
        else:
            logger.warning(f"MAC address {mac_address} not found in database")
            return jsonify(message="MAC address not found in database"), 404
    else:
        logger.error("MAC address not provided in request")
        return jsonify(message="MAC address not provided"), 400

@app.route("/provision/list", methods=["GET"])
def get_camera_associations():
    logger.info("Received GET request for get_camera_associations")
    
    camera_associations = []

    # Retrieve all camera associations from the MongoDB database
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

def _get_vault_token():
    """
    Helper function to retrieve the Vault token from Redis.

    This function retrieves the Vault root token from Redis, which is used for authentication
    when making requests to Vault for retrieving secrets.

    Returns:
        str: The Vault root token.
        
    Raises:
        Exception: If the Vault token is not found in Redis or an error occurs during retrieval.
    """
    try:
        token = redis_client.get("vault_root_token")
        if token:
            return token.decode("utf-8")
        else:
            raise Exception("Vault token not found in Redis")
    except Exception as e:
        raise Exception("Error retrieving Vault token from Redis", e)
    

def _get_stored_password(mac_address):
    """
    Helper function to retrieve the stored password for a MAC address from Vault.

    This function makes a request to Vault to retrieve the stored password for a MAC address.
    It requires the Vault root token for authentication.

    Args:
        mac_address (str): The MAC address of the device.
        vault_token (str): The Vault root token for authentication.

    Returns:
        str: The stored password for the MAC address.

    Raises:
        Exception: If an error occurs during retrieval.
    """
    try:
        # Remove colons from MAC address
        mac_address = mac_address.replace(":", "")
        client = hvac.Client(url=VAULT_ADDRESS, token=_get_vault_token())
        secret = client.secrets.kv.read_secret(
            path="fog-nodes-v1/" + mac_address
        )
        stored_password = secret["data"]["data"]
        return stored_password
    except Exception as e:
        raise Exception("Error retrieving stored password from Vault", e)

if __name__ == "__main__":
    # Start the Flask application
    app.run(host="0.0.0.0", port=5001)
