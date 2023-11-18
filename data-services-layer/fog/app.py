import datetime
import logging
from common.helpers import generate_response
from flask import Flask, request
import hashlib
import uuid
import os
import redis
from bson import ObjectId
from pymongo import MongoClient
import hvac
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Flask(__name__)

BASE_URL_PREFIX = "/fog"

# Redis Configuration
REDIS_HOST = os.environ.get("REDIS_HOST", "redis")
REDIS_PORT = int(os.environ.get("REDIS_PORT", 6379))
redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0)
# Vault Configuration
VAULT_ADDRESS = os.environ.get("VAULT_ADDRESS", "http://vault:8200")
# MongoDB Configuration
MONGO_CONNECTION_URL = os.environ.get("MONGO_CONNECTION_URL", "mongodb://localhost:27017/")
MONGO_DB = os.environ.get("MONGO_DB", "db")
mongo_client = MongoClient(MONGO_CONNECTION_URL)
db = mongo_client[MONGO_DB]


@app.route(f"{BASE_URL_PREFIX}/get-challenge", methods=['POST'])
def get_challenge():
    """
    Endpoint to generate a CHAP challenge for a MAC address.

    This endpoint generates a CHAP (Challenge-Handshake Authentication Protocol) challenge for a given MAC address.
    The challenge is generated as a UUID (Universally Unique Identifier), and it is stored in Redis alongside
    the hashed combination of the stored password, the generated challenge, and the code hash retrieved from Vault.
    The stored challenge has a 2-minute expiration.

    Request JSON Payload:
    {
        "mac_address": "MAC_ADDRESS"
    }

    Response:
    {
        "challenge": "CHALLENGE_UUID"
    }
    """
    try:
        data = request.get_json()
        mac_address = data.get('mac_address')
        vault_token = _get_vault_token()
        logger.info(f"Vault token obtained: {vault_token}")

        stored_password = _get_stored_password(mac_address, vault_token)
        code_hash = _get_code_hash(mac_address, vault_token)

        challenge = str(uuid.uuid4())  # Generate challenge

        # Store the CHAP challenge result in Redis with a 2-minute expiration
        redis_key = f"{mac_address}_challenge"
        redis_client.set(redis_key, hashlib.sha256((stored_password + challenge + code_hash).encode()).hexdigest(), ex=120)

        # Log the challenge and generated UUID
        logger.info(f"Challenge generated for MAC {mac_address}: {challenge}")

        # Return the challenge in a consistent JSON response
        return generate_response("success", "Challenge generated successfully", challenge=challenge), 200
    except Exception as e:
        logger.error(f"Error in 'get_challenge' route: {str(e)}")
        return generate_response("error", str(e)), 500


# Retrieve the stored password for a device based on its MAC address
@app.route(f"{BASE_URL_PREFIX}/get-password", methods=["GET"])
def get_node_password():
    """
    Retrieve the stored password for a device based on its MAC address.

    This endpoint allows retrieving the password associated with a device identified by its MAC address.
    The MAC address is provided as a query parameter in the GET request. The server obtains a Vault token
    for secure authentication, then calls the _get_stored_password function to retrieve the node password
    from a secure storage. The retrieved node password is returned in a JSON response with a success status.

    Endpoint:
        GET /api/v1/get-password?mac_address=MAC_ADDRESS

    Query Parameters:
        - mac_address (string): The MAC address of the device for which the password is to be retrieved.

    Response:
        On success:
        {
            "status": "success",
            "message": "Node password retrieved successfully",
            "fog_password": "RETRIEVED_PASSWORD"
        }

        On error (password not found):
        {
            "status": "error",
            "message": "Node password not found"
        }

        On error (MAC address not provided):
        {
            "status": "error",
            "message": "MAC address not provided in the request"
        }
    """
    logger.info("Received GET request for get_node_password")
    # Get MAC address from the request's query parameters
    mac_address = request.args.get("mac_address")
    if mac_address:
        logger.debug(f"MAC address provided: {mac_address}")
        vault_token = _get_vault_token()
        logger.info(f"vault token obtained: {vault_token}")
        # Call the _get_node_password function to retrieve the node password
        node_password = _get_stored_password(mac_address, vault_token)
        if node_password:
            logger.info(f"Node password retrieved for MAC {mac_address}")
            # Return a JSON response with a success status
            return generate_response("success", "Node password retrieved successfully", fog_password=node_password), 200
        else:
            logger.warning("Node password not found")
            # Return a JSON response with an error status and message
            return generate_response("error", "Node password not found"), 404
    else:
        logger.error("MAC address not provided in request")
        # Return a JSON response with a bad request status and message
        return generate_response("error", "MAC address not provided in the request"), 400

@app.route(f"{BASE_URL_PREFIX}/authenticate", methods=['POST'])
def authenticate():
    """
    Endpoint to authenticate a CHAP response for a MAC address.

    This endpoint is used to authenticate a client's CHAP (Challenge-Handshake Authentication Protocol) response.
    The client sends their MAC address, CHAP response, public IP, coordinates (latitude, longitude), and full location address.
    The server retrieves the stored challenge, validates the response, and if successful,
    generates a session UUID and stores it in Redis with a 1-hour expiration. Additionally, the information is stored
    in a MongoDB collection for monitoring and reviewing sessions created by Fog nodes.

    Request JSON Payload:
    {
        "mac_address": "MAC_ADDRESS",
        "client_response": "CHAP_RESPONSE",
        "public_ip": "CLIENT_PUBLIC_IP",
        "coords": {"latitude": 12.3456, "longitude": -78.9012},
        "location_address": "FULL_LOCATION_ADDRESS"
    }

    Response:
    {
        "message": "Authentication successful",
        "session_id": "SESSION_UUID"
    }
    or
    {
        "message": "Authentication failed"
    }
    """
    try:
        data = request.get_json()
        mac_address = data.get('mac_address')
        client_response = data.get('client_response')
        public_ip = data.get('public_ip')
        coords = data.get('coords')
        location_address = data.get('location_address')
        
        # Retrieve the password + challenge from Redis
        redis_key = f"{mac_address}_challenge"
        stored_result = redis_client.get(redis_key)

        # Delete the challenge key from Redis regardless of authentication outcome
        redis_client.delete(redis_key)

        if stored_result:
            expected_response = stored_result.decode('utf-8')
            if client_response == expected_response:
                # Generate a unique UUID for the session
                session_uuid = str(uuid.uuid4())
                # Store authenticated session UUID in Redis with a 1-hour expiration  - 3600
                redis_session_key = f"{mac_address}_session"
                redis_client.set(redis_session_key, session_uuid, ex=60)
                logger.info(f"Authentication successful for MAC {mac_address}. Session ID: {session_uuid} with session key: {redis_session_key}")
                # Save session information
                session_data = {
                    'mac_address': mac_address,
                    'public_ip': public_ip,
                    'coords': coords,
                    'location_address': location_address,
                    'timestamp': datetime.now()
                }
                db.sessions.insert_one(session_data)
                return generate_response("success", "Authentication successful", session_id=session_uuid), 200
            else:
                logger.info(f"Authentication failed for MAC {mac_address}")
                return generate_response("error", "Authentication failed"), 401
        else:
            logger.warning(f"Challenge not found for MAC {mac_address}")
            return generate_response("error", "Challenge not found"), 404
    except Exception as e:
        logger.error(f"Error in 'authenticate' route: {str(e)}")
        return generate_response("error", str(e)), 500
    
@app.route(f"{BASE_URL_PREFIX}/check-session", methods=['GET'])
def check_session():
    """
    Endpoint to check if a session is active for a MAC address.

    This endpoint checks if there is an active session for a given MAC address.
    If an active session exists, it responds with a message indicating that the session is active.
    If there is no active session, it responds with a 401 Unauthorized status code.

    Request Query Parameters:
    - mac_address (string): MAC address of the device.

    Response (on active session):
    {
        "message": "Session is active"
    }
    Response (on no active session):
    401 Unauthorized
    """
    try:
        mac_address = request.args.get('mac_address')
        logger.info(f"Checking session for MAC {mac_address}. Redis session key: {mac_address}_session")
        # Check if an active session exists for the MAC address
        redis_session_key = f"{mac_address}_session"
        ttl = redis_client.ttl(redis_session_key)
        print(f"Time remaining for {redis_session_key}: {ttl} seconds")
        session_id = redis_client.get(redis_session_key)
        if session_id:
            logger.info(f"Session is active for MAC {mac_address}")
            return generate_response("success", "Session is active"), 200
        else:
            logger.info(f"No active session for MAC {mac_address}")
            return generate_response("error", "Unauthorized"), 401
    except Exception as e:
        logger.error(f"Error in 'check_session' route: {str(e)}")
        return generate_response("error", str(e)), 500
    
# Provision camera information based on the MAC address
@app.route(f"{BASE_URL_PREFIX}/provision", methods=["GET"])
def get_node_provision():
    """
    Provision camera information based on the MAC address.

    This endpoint retrieves provisioning information for a device based on its MAC address.
    The provisioning process involves checking the status in the provisioning database, 
    verifying the provisioning status, retrieving the associated camera information, 
    and ensuring the authentication using a session ID.

    Request Query Parameters:
    - mac_address (string): MAC address of the device.

    Response:
    - 200 OK: Node provisioned successfully. Returns camera information.
    - 400 Bad Request: MAC address not provided in the request.
    - 403 Forbidden: Provisioning status is not enabled for the specified MAC address.
    - 404 Not Found: MAC address or camera information not found in the database.
    - 401 Unauthorized: Invalid session ID or session ID not provided.

    Example:
    GET http://localhost:5000/provision?mac_address=02:42:ac:11:00:02
    Headers: X-Session-ID: <valid_session_id>

    Response:
    {
        "status": "success",
        "message": "Node provisioned successfully",
        "data": {
            "camera_id": "CAMERA_ID",
            "camera_url": "http://camera.example.com",
            "camera_url_params": "resolution=720p",
            "camera_username": "admin",
            "camera_password": "secure_password"
        }
    }
    """
    logger.info("Received GET request for get_node_provision")
    
    # Get MAC address from the request's query parameters
    mac_address = request.args.get("mac_address")

    if not mac_address:
        return generate_response("error", "MAC address not provided in the request"), 400

    logger.info(f"MAC address provided: {mac_address}")
    
    # Retrieve provisioning information from the MongoDB database
    provisioning_info = db.provisioning.find_one({"mac_address": mac_address})

    if not provisioning_info:
        return generate_response("error", f"MAC address {mac_address} not found in the provisioning database"), 404

    logger.info(f"Provisioning info found for MAC {mac_address}")

    # Check provisioning status
    provisioning_status = provisioning_info.get("status")

    if provisioning_status != "enabled":
        return generate_response("error", f"Provisioning status is not enabled for MAC {mac_address}"), 403

    # Retrieve camera_id from provisioning information
    camera_id = provisioning_info.get("camera_id")
    # Retrieve camera information from the MongoDB database
    camera_info = db.cameras.find_one({"_id": ObjectId(camera_id)})

    if not camera_info:
        return generate_response("error", f"Camera information not found for camera_id {camera_id}"), 404

    logger.info(f"Camera info found for camera_id {camera_id}")

    # Extract camera details
    camera_url = camera_info.get("camera_url")
    camera_url_params = camera_info.get("camera_url_params")
    camera_username = camera_info.get("camera_username")
    camera_password = camera_info.get("camera_password")

    # Check the X-Session-ID header for authentication
    session_id = request.headers.get("X-Session-ID")

    if not session_id:
        return generate_response("error", "Session ID not provided"), 400

    logger.info(f"Session ID provided: {session_id}")
    redis_session_key = f"{mac_address}_session"
    stored_session_id = redis_client.get(redis_session_key)

    if not stored_session_id or stored_session_id.decode("utf-8") != session_id:
        return generate_response("error", "Invalid session ID"), 401

    logger.info(f"Session ID {session_id} matches the one stored in Redis")

    return generate_response("success", "Node provisioned successfully", 
                            data={
                                "camera_id": camera_id,
                                "camera_url": camera_url, 
                                "camera_url_params": camera_url_params, 
                                "camera_username": camera_username, 
                                "camera_password": camera_password
                            }), 200

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
    

def _get_stored_password(mac_address, vault_token):
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
        client = hvac.Client(url=VAULT_ADDRESS, token=vault_token)
        secret = client.secrets.kv.read_secret(
            path="fog-nodes-v1/" + mac_address
        )
        stored_password = secret["data"]["data"]
        return stored_password
    except Exception as e:
        raise Exception("Error retrieving stored password from Vault", e)

    
def _get_code_hash(mac_address, vault_token):
    """
    Helper function to retrieve the code hash for a MAC address from Vault.

    This function makes a request to Vault to retrieve the code hash associated with a MAC address.
    It requires the Vault root token for authentication.

    Args:
        mac_address (str): The MAC address of the device.
        vault_token (str): The Vault root token for authentication.

    Returns:
        str: The code hash associated with the MAC address.

    Raises:
        Exception: If an error occurs during retrieval.
    """
    try:
        # Remove colons from MAC address
        mac_address = mac_address.replace(":", "")
        client = hvac.Client(url=VAULT_ADDRESS, token=vault_token)
        secret = client.secrets.kv.read_secret(
            path="fog-nodes-v1/" + mac_address
        )
        code_hash = secret["data"]["code_hash"]
        return code_hash
    except Exception as e:
        raise Exception("Error retrieving code hash from Vault", e)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
