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

BASE_URL_PREFIX = "/provision"
# Redis Configuration
REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
REDIS_PORT = int(os.environ.get("REDIS_PORT", 6379))
redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT)
VAULT_ADDRESS = os.environ.get("VAULT_ADDRESS", "http://vault:8200")
# MongoDB Configuration
MONGO_CONNECTION_URL = os.environ.get("MONGO_CONNECTION_URL", "mongodb://localhost:27017/")
MONGO_DB = os.environ.get("MONGO_DB", "db")
mongo_client = MongoClient(MONGO_CONNECTION_URL)
db = mongo_client[MONGO_DB]


# Provision camera information based on the MAC address
@app.route(f"{BASE_URL_PREFIX}/node", methods=["GET"])
def get_node_provision():
    logger.info("Received GET request for get_node_provision")
    
    # Get MAC address from the request's query parameters
    mac_address = request.args.get("mac_address")

    if mac_address:
        logger.info(f"MAC address provided: {mac_address}")
        # Retrieve camera information from the MongoDB database
        camera_info = db.provisioning.find_one({"mac_address": mac_address})

        if camera_info:
            logger.info(f"Camera info found for MAC {mac_address}")
            # Extract camera details
            camera_url = camera_info.get("camera_url")
            camera_url_params = camera_info.get("camera_url_params")
            camera_username = camera_info.get("camera_username")
            camera_password = camera_info.get("camera_password")

            # Check the X-Session-ID header for authentication
            session_id = request.headers.get("X-Session-ID")
            if session_id:
                logger.info(f"Session ID provided: {session_id}")
                redis_session_key = f"{mac_address}_session"
                stored_session_id = redis_client.get(redis_session_key)

                if stored_session_id and stored_session_id.decode("utf-8") == session_id:
                    logger.info(f"Session ID {session_id} matches the one stored in Redis")
                    # Remove the stored session key after successful provisioning
                    redis_client.delete(redis_session_key)
                    response = {
                        "status": "success",
                        "message": "Node provisioned successfully",
                        "camera_url": camera_url,
                        "camera_url_params": camera_url_params,
                        "camera_username": camera_username,
                        "camera_password": camera_password
                    }
                    return jsonify(response), 200
                else:
                    logger.warning("Invalid session ID")
                    response = {
                        "status": "error",
                        "message": "Invalid session ID"
                    }
                    return jsonify(response), 401
            else:
                logger.error("Session ID not provided")
                response = {
                    "status": "error",
                    "message": "Session ID not provided"
                }
                return jsonify(response), 400
        else:
            logger.warning(f"MAC address {mac_address} not found in the database")
            response = {
                "status": "error",
                "message": "MAC address not found in the database"
            }
            return jsonify(response), 404
    else:
        logger.error("MAC address not provided in the request")
        response = {
            "status": "error",
            "message": "MAC address not provided in the request"
        }
        return jsonify(response), 400

# Provision a new camera association
@app.route(f"{BASE_URL_PREFIX}/node", methods=["POST"])
def provision_node():
    logger.info("Received POST request for provision_node")
    
    # Get JSON data from the request's body
    data = request.get_json()

    mac_address = data.get("mac_address")
    camera_url = data.get("camera_url")
    camera_url_params = data.get("camera_url_params")
    camera_username = data.get("camera_username")
    camera_password = data.get("camera_password")

    if not mac_address or not camera_url or not camera_url_params:
        logger.error("Missing required data in request body")
        response = {
            "status": "error",
            "message": "Missing required data"
        }
        return jsonify(response), 400

    existing_camera = db.provisioning.find_one({"mac_address": mac_address})
    if existing_camera:
        logger.warning("MAC address already exists in the database")
        response = {
            "status": "error",
            "message": "MAC address already exists in the database"
        }
        return jsonify(response), 409

    # Insert camera information into the MongoDB database
    db.provisioning.insert_one(
        {
            "mac_address": mac_address,
            "camera_url": camera_url,
            "camera_url_params": camera_url_params,
            "camera_username": camera_username,
            "camera_password": camera_password,
        }
    )

    logger.info(f"Node provisioned successfully for MAC {mac_address}")
    response = {
        "status": "success",
        "message": "Node provisioned successfully"
    }
    return jsonify(response), 201

# Remove a camera association based on the MAC address
@app.route(f"{BASE_URL_PREFIX}/node", methods=["DELETE"])
def remove_node_provision():
    logger.info("Received DELETE request for remove_node_provision")

    # Get MAC address from the request's query parameters
    mac_address = request.args.get("mac_address")

    # Initialize the response dictionary
    response = {"status": "success", "message": "", "data": {}}

    if mac_address:
        logger.debug(f"MAC address provided: {mac_address}")
        # Check if the MAC address exists in the MongoDB database
        camera_info = db.provisioning.find_one({"mac_address": mac_address})

        if camera_info:
            # Delete the camera association from the MongoDB database
            db.provisioning.delete_one({"mac_address": mac_address})
            logger.info(f"Camera association removed for MAC {mac_address}")
            response["message"] = "Node provision removed"
            return jsonify(response), 200
        else:
            logger.warning(f"MAC address {mac_address} not found in database")
            response["status"] = "error"
            response["message"] = "MAC address not found in the database"
            return jsonify(response), 404
    else:
        logger.error("MAC address not provided in request")
        response["status"] = "error"
        response["message"] = "MAC address not provided"
        return jsonify(response), 400


# Get a list of all camera associations
@app.route(f"{BASE_URL_PREFIX}/list", methods=["GET"])
def get_node_provision_list():
    logger.info("Received GET request for get_node_provision_list")

    # Initialize the response dictionary
    response = {"status": "success", "message": "Node provisions retrieved successfully", "data": []}

    # Retrieve all camera associations from the MongoDB database
    cursor = db.provisioning.find({})
    for camera_info in cursor:
        camera_associations = {
            "mac_address": camera_info.get("mac_address"),
            "camera_url": camera_info.get("camera_url"),
            "camera_url_params": camera_info.get("camera_url_params"),
            "camera_username": camera_info.get("camera_username"),
            "camera_password": camera_info.get("camera_password"),
        }
        response["data"].append(camera_associations)

    return jsonify(response), 200


@app.route("/update-gps-info", methods=["POST"])
def update_gps_info():
    logger.info("Received POST request for update_gps_info")
    
    data = request.get_json()

    mac_address = data.get("mac_address")
    gps_info = data.get("gps_info")

    if not mac_address or not gps_info:
        logger.error("Missing required data in request body")
        response = {
            "status": "error",
            "message": "Missing required data"
        }
        return jsonify(response), 400

    # Update the MongoDB document with the new GPS information
    result = db.provisioning.update_one({"mac_address": mac_address}, {"$set": {"gps_info": gps_info}})
    
    if result.modified_count == 1:
        logger.info(f"GPS information updated for MAC {mac_address}")
        response = {
            "status": "success",
            "message": "GPS information updated successfully"
        }
        return jsonify(response), 200
    else:
        logger.warning(f"MAC address {mac_address} not found in the database")
        response = {
            "status": "error",
            "message": "MAC address not found in the database"
        }
        return jsonify(response), 404


if __name__ == "__main__":
    # Start the Flask application
    app.run(host="0.0.0.0", port=5000)
