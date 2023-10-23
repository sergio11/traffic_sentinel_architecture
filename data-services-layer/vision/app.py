import logging
from flask import Flask, request, jsonify
from pymongo import MongoClient
import os
from datetime import datetime
from common.requires_authentication_decorator import requires_authentication

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
# MongoDB Configuration
MONGO_CONNECTION_URL = os.environ.get("MONGO_CONNECTION_URL", "mongodb://localhost:27017/")
MONGO_DB = os.environ.get("MONGO_DB", "db")
mongo_client = MongoClient(MONGO_CONNECTION_URL)
db = mongo_client[MONGO_DB]

DEFAULT_PAGE_SIZE = 10

app = Flask(__name__)

@app.route('/frames', methods=['GET'])
@requires_authentication()
def get_frames():
    """
    Endpoint to retrieve paginated frames captured and processed during a specified time interval for a given MAC address.

    This endpoint allows users to retrieve a paginated list of frames captured and processed within a specified time range
    for a specific MAC address. The frames are stored in the MongoDB collection.

    Request Parameters:
    - mac_address (str): The MAC address for which frames are to be retrieved.
    - start_time (str): The start time of the time interval (in ISO 8601 format).
    - end_time (str): The end time of the time interval (in ISO 8601 format).
    - page (int, optional): The page number for pagination (default is 1).
    - page_size (int, optional): The number of frames to include on each page (default is 10).

    Response:
    {
        "frames": [
            {
                "mac_address": "MAC_ADDRESS",
                "camera_provisioning_id": "CAMERA_ID",
                "timestamp": "TIMESTAMP",
                "frame_url": "FRAME_URL",
                "vehicles": [
                    {
                        "vehicle_id": "TRACK_ID",
                        "direction": "DIRECTION",
                        "color": "COLOR_LABEL",
                        "timestamp": "TIMESTAMP",
                        "speed_kmph": "SPEED_KMPH",
                        "roi_base64": "ROI_BASE64",
                        "license_plate": "LICENSE_PLATE"
                    },
                    ...
                ]
            },
            ...
        ]
    }

    Example Request:
    GET /frames?mac_address=MAC_ADDRESS&start_time=2023-01-01T00:00:00Z&end_time=2023-01-02T00:00:00Z&page=1&page_size=10

    Example Response:
    {
        "frames": [
            {
                "mac_address": "MAC_ADDRESS",
                "camera_provisioning_id": "CAMERA_ID",
                "timestamp": "TIMESTAMP",
                "frame_url": "FRAME_URL",
                "vehicles": [
                    {
                        "vehicle_id": "TRACK_ID",
                        "direction": "DIRECTION",
                        "color": "COLOR_LABEL",
                        "timestamp": "TIMESTAMP",
                        "speed_kmph": "SPEED_KMPH",
                        "roi_base64": "ROI_BASE64",
                        "license_plate": "LICENSE_PLATE"
                    },
                    ...
                ]
            },
            ...
        ]
    }
    """
    mac_address = request.args.get('mac_address')
    start_time = request.args.get('start_time')
    end_time = request.args.get('end_time')
    page = int(request.args.get('page', 1))  # Current page
    page_size = int(request.args.get('page_size', DEFAULT_PAGE_SIZE))  # Page size

    # Validate query parameters
    if not (mac_address and start_time and end_time):
        return jsonify(message="Missing required query parameters"), 400

    try:
        start_time = datetime.fromisoformat(start_time)
        end_time = datetime.fromisoformat(end_time)
    except ValueError:
        return jsonify(message="Invalid datetime format. Use ISO 8601 format."), 400

    # Query the database to retrieve frames within the specified time range for the MAC address
    query = {
        "mac_address": mac_address,
        "timestamp": {"$gte": start_time, "$lte": end_time}
    }
    frames = list(db.frames.find(query, {"_id": 0}).skip((page - 1) * page_size).limit(page_size))

    return jsonify(frames=frames)


if __name__ == "__main__":
    # Start the Flask application
    app.run(host="0.0.0.0", port=5002)
