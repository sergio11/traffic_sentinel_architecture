import logging
from flask import Flask, request, jsonify
from pymongo import MongoClient
import os
from datetime import datetime
from common.requires_authentication_decorator import requires_authentication
from minio import Minio

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
# MongoDB Configuration
MONGO_CONNECTION_URL = os.environ.get("MONGO_CONNECTION_URL", "mongodb://localhost:27017/")
MONGO_DB = os.environ.get("MONGO_DB", "db")
mongo_client = MongoClient(MONGO_CONNECTION_URL)
db = mongo_client[MONGO_DB]

MINIO_ENDPOINT = os.environ.get("MINIO_ENDPOINT", "minio-server:9000")
MINIO_ACCESS_KEY = os.environ.get("MINIO_ACCESS_KEY", "your-access-key")
MINIO_SECRET_KEY = os.environ.get("MINIO_SECRET_KEY", "your-secret-key")
MINIO_BUCKET = "frames-bucket"

minio_client = Minio(MINIO_ENDPOINT, access_key=MINIO_ACCESS_KEY, secret_key=MINIO_SECRET_KEY, secure=False)


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


@app.route('/process_frame', methods=['POST'])
def process_frame():
    try:
        data = request.json
        mac_address = data.get("mac_address")
        timestamp = data.get("timestamp")
        frame_data = data.get("frame_data")

        # Check if the required data is provided
        if not (mac_address and timestamp and frame_data):
            return jsonify(message="Missing required data"), 400

        # Convert the timestamp to a datetime object
        timestamp = datetime.fromtimestamp(timestamp)

        # Save the images to MinIO and get the URLs
        frame_data["annotated_frame_url"] = save_image_to_minio(frame_data["annotated_frame_base64"])
        frame_data["original_frame_url"] = save_image_to_minio(frame_data["original_frame_base64"])
        for vehicle in frame_data["detected_vehicles"]:
            vehicle["vehicle_frame_url"] = save_image_to_minio(vehicle["vehicle_frame_base64"])

        # Remove Base64 representations of the images
        frame_data.pop("annotated_frame_base64", None)
        frame_data.pop("original_frame_base64", None)
        for vehicle in frame_data["detected_vehicles"]:
            vehicle.pop("vehicle_frame_base64", None)

        # Insert the JSON into the MongoDB collection
        db.frames.insert_one({
            "mac_address": mac_address,
            "timestamp": timestamp,
            "frame_data": frame_data
        })

        return jsonify(message="Frame processed successfully"), 200

    except Exception as e:
        return jsonify(message="Error processing frame", error=str(e)), 500


def save_image_to_minio(base64_data):
    # Generate a unique object name in MinIO
    object_name = f"{datetime.now().isoformat()}.jpg"

    # Decode the Base64 data and store the image in MinIO
    minio_client.put_object(MINIO_BUCKET, object_name, base64_data.encode(), len(base64_data))

    # Return the URL of the image in MinIO
    presigned_url = minio_client.presigned_get_object(MINIO_BUCKET, object_name)
    return presigned_url


if __name__ == "__main__":
    # Start the Flask application
    app.run(host="0.0.0.0", port=5002)
