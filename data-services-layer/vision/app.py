import base64
import io
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

# Base prefix for application routes
BASE_URL_PREFIX = "/vision"

# MongoDB Configuration
MONGO_CONNECTION_URL = os.environ.get("MONGO_CONNECTION_URL", "mongodb://localhost:27017/")
MONGO_DB = os.environ.get("MONGO_DB", "db")
mongo_client = MongoClient(MONGO_CONNECTION_URL)
db = mongo_client[MONGO_DB]

# MinIO Configuration
MINIO_ENDPOINT = os.environ.get("MINIO_ENDPOINT", "minio-server:9000")
MINIO_ACCESS_KEY = os.environ.get("MINIO_ACCESS_KEY", "your-access-key")
MINIO_SECRET_KEY = os.environ.get("MINIO_SECRET_KEY", "your-secret-key")
MINIO_BUCKET = os.environ.get("MINIO_BUCKET", "frames-bucket")

# Default page size for pagination in the application
DEFAULT_PAGE_SIZE = 10

app = Flask(__name__)

@app.route(f"{BASE_URL_PREFIX}/frames/list", methods=['GET'])
@requires_authentication()
def get_frames():
    try:
        logger.info("Received GET request for frames list.")
        mac_address = request.args.get('mac_address')
        start_time = request.args.get('start_time')
        end_time = request.args.get('end_time')
        page = int(request.args.get('page', 1))  # Current page
        page_size = int(request.args.get('page_size', DEFAULT_PAGE_SIZE))  # Page size

        logger.debug(f"Request parameters: mac_address={mac_address}, start_time={start_time}, end_time={end_time}, page={page}, page_size={page_size}")

        # Validate query parameters
        if not (mac_address and start_time and end_time):
            logger.warning("Missing required query parameters.")
            return jsonify(message="Missing required query parameters"), 400

        start_time = datetime.fromisoformat(start_time)
        end_time = datetime.fromisoformat(end_time)

        query = {
            "mac_address": mac_address,
            "timestamp": {"$gte": start_time, "$lte": end_time}
        }

        frames = list(db.frames.find(query, {"_id": 0}).skip((page - 1) * page_size).limit(page_size))
        
        logger.debug(f"Retrieved frames: {frames}")

        return jsonify(frames=frames)

    except Exception as e:
        logger.error(f"Error in get_frames: {str(e)}")
        return jsonify(message="Error processing request"), 500


@app.route(f"{BASE_URL_PREFIX}/frames/save", methods=['POST'])
def save_frame():
    try:
        logger.info("Received POST request for saving frames.")
        data = request.json
        mac_address = data.get("mac_address")
        processed_frame = eval(data.get("processed_frame"))  # Use eval to convert string to dictionary

        if not (mac_address and processed_frame):
            logger.warning("Missing required data.")
            return jsonify(message="Missing required data"), 400

        logger.debug(f"Request data: mac_address={mac_address}")

        timestamp = datetime.now()

        # Save the images to MinIO and get the URLs
        processed_frame["annotated_frame_name"] = save_image_to_minio(processed_frame["annotated_frame_base64"])
        processed_frame["original_frame_name"] = save_image_to_minio(processed_frame["original_frame_base64"])
        
        for vehicle in processed_frame["detected_vehicles"]:
            vehicle["vehicle_frame_name"] = save_image_to_minio(vehicle["vehicle_frame_base64"])

        processed_frame.pop("annotated_frame_base64", None)
        processed_frame.pop("original_frame_base64", None)

        for vehicle in processed_frame["detected_vehicles"]:
            vehicle.pop("vehicle_frame_base64", None)

        db.frames.insert_one({
            "mac_address": mac_address,
            "processed_timestamp": timestamp,
            "processed_frame": processed_frame
        })

        logger.info("Frame processed successfully.")
        return jsonify(message="Frame processed successfully"), 200

    except Exception as e:
        logger.error(f"Error in save_frame: {str(e)}")
        return jsonify(message="Error processing frame"), 500


def save_image_to_minio(base64_data):
    # Decode the Base64 data
    image_data = base64.b64decode(base64_data)

    # Generate a unique object name in MinIO
    object_name = f"{datetime.now().isoformat()}.jpg"

    # Initialize MinIO client
    minio_client = Minio(MINIO_ENDPOINT, access_key=MINIO_ACCESS_KEY, secret_key=MINIO_SECRET_KEY, secure=False)

    # Check if the MinIO bucket exists; create if not
    bucket_exists = minio_client.bucket_exists(MINIO_BUCKET)
    if not bucket_exists:
        logger.info(f"Bucket '{MINIO_BUCKET}' does not exist; creating...")
        minio_client.make_bucket(MINIO_BUCKET)

    # Store the image in MinIO
    minio_client.put_object(MINIO_BUCKET, object_name, io.BytesIO(image_data), len(image_data))

    return object_name


if __name__ == "__main__":
    # Start the Flask application
    app.run(host="0.0.0.0", port=5000)
