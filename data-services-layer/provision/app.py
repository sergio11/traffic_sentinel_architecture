import datetime
import logging
from common.helpers import generate_response
from flask import Flask, request
from pymongo import MongoClient
import os

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Flask(__name__)

BASE_URL_PREFIX = "/provisioning"
# MongoDB Configuration
MONGO_CONNECTION_URL = os.environ.get("MONGO_CONNECTION_URL", "mongodb://localhost:27017/")
MONGO_DB = os.environ.get("MONGO_DB", "db")
mongo_client = MongoClient(MONGO_CONNECTION_URL)
db = mongo_client[MONGO_DB]


@app.route(f"{BASE_URL_PREFIX}/register", methods=['POST'])
def create_provisioning():
    """
    Creates a provisioning document linking a MAC Address to a camera.
    """
    try:
        data = request.json
        mac_address = data.get("mac_address")
        camera_id = data.get("camera_id")

        # Check if required data is missing
        if not (mac_address and camera_id):
            return generate_response("error", "Missing required data"), 400

        # Prepare provisioning data
        provisioning_data = {
            "mac_address": mac_address,
            "camera_id": camera_id,
            "status": "enabled",  # Set default status to "enabled"
            "timestamp": datetime.now()
        }

        # Insert provisioning data into the database
        db.provisioning.insert_one(provisioning_data)

        # Return success response
        return generate_response("success", "Provisioning created successfully"), 201

    except Exception as e:
        # Log and return an error response if an exception occurs
        logger.error(f"Error in create_provisioning: {str(e)}")
        return generate_response("error", "Error creating provisioning"), 500


@app.route(f"{BASE_URL_PREFIX}/<mac_address>", methods=['PUT'])
def toggle_provisioning(mac_address):
    """
    Enables or disables provisioning for a MAC Address.
    """
    try:
        # Find the provisioning entry in the database
        provisioning_entry = db.provisioning.find_one({"mac_address": mac_address})

        # Check if provisioning entry exists
        if not provisioning_entry:
            return generate_response("error", "Provisioning not found"), 404

        # Toggle provisioning status
        current_status = provisioning_entry["status"]
        new_status = "disabled" if current_status == "enabled" else "enabled"

        # Update the provisioning status in the database
        db.provisioning.update_one({"mac_address": mac_address}, {"$set": {"status": new_status}})

        # Return success response
        return generate_response("success", f"Provisioning {new_status} successfully"), 200

    except Exception as e:
        # Log and return an error response if an exception occurs
        logger.error(f"Error in toggle_provisioning: {str(e)}")
        return generate_response("error", "Error toggling provisioning status"), 500


@app.route(f"{BASE_URL_PREFIX}/<mac_address>", methods=['DELETE'])
def delete_provisioning(mac_address):
    """
    Deletes provisioning for a MAC Address.
    """
    try:
        # Delete the provisioning entry from the database
        result = db.provisioning.delete_one({"mac_address": mac_address})

        # Check if the provisioning entry was not found
        if result.deleted_count == 0:
            return generate_response("error", "Provisioning not found"), 404

        # Return success response
        return generate_response("success", "Provisioning deleted successfully"), 200

    except Exception as e:
        # Log and return an error response if an exception occurs
        logger.error(f"Error in delete_provisioning: {str(e)}")
        return generate_response("error", "Error deleting provisioning"), 500

if __name__ == "__main__":
    # Start the Flask application
    app.run(host="0.0.0.0", port=5000)
