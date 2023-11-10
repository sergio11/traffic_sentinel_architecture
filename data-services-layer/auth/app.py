import logging
from common.requires_authentication_decorator import requires_authentication
from flask import Flask, request, jsonify
import hashlib
import uuid
import os
import jwt
import redis
from pymongo import MongoClient, DESCENDING
import hvac

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Flask(__name__)

BASE_URL_PREFIX = "/auth"

JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "secret_key")
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


# Endpoint to register new users (only administrators can do this)
@app.route(f"{BASE_URL_PREFIX}/users/register", methods=['POST'])
@requires_authentication(required_role="admin")
def register_user():
    try:
        data = request.get_json()
        role = data.get('role')
        username = data.get('username')
        password = data.get('password')

        # Check if the role is valid (either "operator" or "admin")
        if role not in ("operator", "admin"):
            return jsonify(message='Invalid role'), 400

        # Check if username and password are not empty
        if not username or not password:
            return jsonify(message='Username and password are required'), 400

        # Check if the user already exists
        existing_user = db.users.find_one({"username": username})

        if existing_user:
            return jsonify(message='User already exists'), 400

        # Hash the password before storing it
        hashed_password = hashlib.sha256(password.encode()).hexdigest()

        # Create a new user document
        new_user = {
            "username": username,
            "password": hashed_password,
            "role": role,
            "enabled": True  # Enable the user by default
        }

        # Insert the new user into the MongoDB collection
        result = db.users.insert_one(new_user)

        if result.inserted_id:
            return jsonify(message='User registered successfully')
        else:
            return jsonify(message='User registration failed'), 500
    except Exception as e:
        return jsonify(message=str(e)), 500

# Endpoint to authenticate users
@app.route(f"{BASE_URL_PREFIX}/users/authenticate", methods=['POST'])
def authenticate_user():
    try:
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')
        user = db.users.find_one({"username": username})
        if user:
            stored_password = user["password"]
            hashed_password = hashlib.sha256(password.encode()).hexdigest()
            if stored_password == hashed_password:
                if user.get("enabled", False):
                    payload = {
                        "username": username,
                        "role": user.get("role", "operator") 
                    }
                    session_token = jwt.encode(payload, JWT_SECRET_KEY, algorithm='HS256')
                    return jsonify(message='Authentication successful', session_token=session_token), 200
                else:
                    return jsonify(message='Authentication failed: User is not enabled'), 401
            else:
                return jsonify(message='Authentication failed: Invalid credentials'), 401
        else:
            return jsonify(message='Authentication failed: User not found'), 404
    except Exception as e:
        return jsonify(message=str(e)), 500

# Endpoint to enable/disable users (only administrators can do this)
@app.route(f"{BASE_URL_PREFIX}/users/toggle-status", methods=['POST'])
@requires_authentication(required_role="admin")
def toggle_user_status():
    try:
        data = request.get_json()
        username = data.get('username')
        status = data.get('status')  # 'enable' or 'disable'

        if status not in ('enable', 'disable'):
            return jsonify(message='Invalid status'), 400

        # Update user status in the database
        db.users.update_one({"username": username}, {"$set": {"enabled": status == 'enable'}})

        return jsonify(message=f'User {username} {status}d successfully')
    except Exception as e:
        return jsonify(message=str(e)), 500

# Endpoint to list all registered users with pagination and sorting
@app.route(f"{BASE_URL_PREFIX}/users/list", methods=['GET'])
@requires_authentication(required_role="admin")
def list_users():
    try:
        page = request.args.get('page', default=1, type=int)
        per_page = request.args.get('per_page', default=10, type=int)
        users = list(
            db.users.find({}, {"_id": 0, "password": 0})
            .sort("registration_date", DESCENDING)
            .skip((page - 1) * per_page)
            .limit(per_page)
        )
        return jsonify(users=users), 200
    except Exception as e:
        return jsonify(message=str(e)), 500


@app.route(f"{BASE_URL_PREFIX}/nodes/get-challenge", methods=['POST'])
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
        logger.info(f"vault token obtained: {vault_token}")
        stored_password = _get_stored_password(mac_address, vault_token)
        code_hash = _get_code_hash(mac_address, vault_token)

        challenge = str(uuid.uuid4())  # Generate challenge

        # Store the CHAP challenge result in Redis with a 2-minute expiration
        redis_key = f"{mac_address}_challenge"
        redis_client.set(redis_key, hashlib.sha256((stored_password + challenge + code_hash).encode()).hexdigest(), ex=120)
        
        # Log the challenge and generated UUID
        logger.info(f"Challenge generated for MAC {mac_address}: {challenge}")

        return jsonify(challenge=challenge)
    except Exception as e:
        logger.error(f"Error in 'get_challenge' route: {str(e)}")
        return jsonify(message=str(e)), 500


# Retrieve the stored password for a device based on its MAC address
@app.route(f"{BASE_URL_PREFIX}/nodes/get-password", methods=["GET"])
def get_node_password():
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
            response = {
                "status": "success",
                "message": "Node password retrieved successfully",
                "fog_password": node_password
            }
            return jsonify(response), 200
        else:
            logger.warning("Node password not found")
            # Return a JSON response with an error status and message
            response = {
                "status": "error",
                "message": "Node password not found"
            }
            return jsonify(response), 404
    else:
        logger.error("MAC address not provided in request")
        # Return a JSON response with a bad request status and message
        response = {
            "status": "error",
            "message": "MAC address not provided in the request"
        }
        return jsonify(response), 400

@app.route(f"{BASE_URL_PREFIX}/nodes/authenticate", methods=['POST'])
def authenticate():
    """
    Endpoint to authenticate a CHAP response for a MAC address.

    This endpoint is used to authenticate a client's CHAP (Challenge-Handshake Authentication Protocol) response.
    The client sends their MAC address and the CHAP response they calculated based on the challenge previously
    generated by the server. The server retrieves the stored challenge, validates the response, and if successful,
    generates a session UUID and stores it in Redis with a 1-hour expiration.

    Request JSON Payload:
    {
        "mac_address": "MAC_ADDRESS",
        "client_response": "CHAP_RESPONSE"
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
                # Store authenticated session UUID in Redis with a 1-hour expiration
                redis_session_key = f"{mac_address}_session"
                redis_client.set(redis_session_key, session_uuid, ex=3600)
                logger.info(f"Authentication successful for MAC {mac_address}. Session ID: {session_uuid} with session key: {redis_session_key}")
                return jsonify(message='Authentication successful', session_id=session_uuid), 200
            else:
                logger.info(f"Authentication failed for MAC {mac_address}")
                return jsonify(message='Authentication failed'), 401
        else:
            logger.warning(f"Challenge not found for MAC {mac_address}")
            return jsonify(message='Challenge not found'), 404
    except Exception as e:
        logger.error(f"Error in 'authenticate' route: {str(e)}")
        return jsonify(message=str(e)), 500
    
@app.route(f"{BASE_URL_PREFIX}/nodes/check-session", methods=['POST'])
def check_session():
    """
    Endpoint to check if a session is active for a MAC address.

    This endpoint checks if there is an active session for a given MAC address.
    If an active session exists, it responds with a message indicating that the session is active.
    If there is no active session, it responds with a 401 Unauthorized status code.

    Request JSON Payload:
    {
        "mac_address": "MAC_ADDRESS"
    }

    Response (on active session):
    {
        "message": "Session is active"
    }
    Response (on no active session):
    401 Unauthorized
    """
    try:
        data = request.get_json()
        mac_address = data.get('mac_address')
        
        # Check if an active session exists for the MAC address
        redis_session_key = f"{mac_address}_session"
        session_id = redis_client.get(redis_session_key)
        if session_id:
            logger.info(f"Session is active for MAC {mac_address}.")
            return jsonify(message='Session is active'), 200
        else:
            logger.info(f"No active session for MAC {mac_address}.")
            return 'Unauthorized', 401
    except Exception as e:
        logger.error(f"Error in 'check_session' route: {str(e)}")
        return jsonify(message=str(e)), 500
    

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
