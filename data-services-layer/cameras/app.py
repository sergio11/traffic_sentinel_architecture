import base64
import io
import logging
from flask import Flask, request, send_file
from pymongo import MongoClient
import os
from datetime import datetime
from common.requires_authentication_decorator import requires_authentication
from minio import Minio
from common.helpers import generate_response
import uuid
from bson import ObjectId

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Base prefix for application routes
BASE_URL_PREFIX = "/cameras"

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

@app.route(f"{BASE_URL_PREFIX}/register", methods=['POST'])
@requires_authentication()
def register_camera():
    """
    Registers a new camera with the specified information.

    Endpoint: POST /cameras/register

    Parameters:
    - camera_name (string): Name of the camera.
    - region (string): Region where the camera is located.
    - address (string): Address of the camera location.
    - max_speed_limit (int): Maximum speed limit for the road monitored by the camera.
    - camera_url (string): URL of the camera.
    - camera_url_params (string): Parameters associated with the camera URL.
    - camera_username (string): Username for camera authentication.
    - camera_password (string): Password for camera authentication.

    Returns:
    - 200 OK: Camera registered successfully. Returns the registered camera information.
    - 400 Bad Request: Missing required data in the request.
    - 409 Conflict: A camera with the same name already exists.
    - 500 Internal Server Error: Error registering the camera.
    """
    try:
        logger.info("Received POST request for registering a new camera.")
        data = request.json
        required_fields = ["camera_name", "region", "address", "max_speed_limit", "camera_url", "camera_url_params", "camera_username", "camera_password"]

        missing_fields = [field for field in required_fields if not data.get(field)]
        if missing_fields:
            logger.warning("Missing required data.")
            return generate_response("error", "Missing required data", missing_fields=missing_fields), 400

        logger.debug(f"Request data: {data}")

        # Check if a camera with the same name already exists
        existing_camera = db.cameras.find_one({"camera_name": data["camera_name"]})
        if existing_camera:
            logger.warning("A camera with the same name already exists.")
            return generate_response("error", "A camera with the same name already exists"), 409

        # Save the camera information to MongoDB
        db.cameras.insert_one(data)

        # Retrieve the newly registered camera information
        new_camera_info = db.cameras.find_one({"camera_name": data["camera_name"]})

        logger.info("Camera registered successfully.")

        # Convert ObjectId to string before JSON serialization
        if new_camera_info and '_id' in new_camera_info:
            new_camera_info['_id'] = str(new_camera_info['_id'])

        return generate_response("success", "Camera registered successfully", camera=new_camera_info), 200

    except Exception as e:
        logger.error(f"Error in register_camera: {str(e)}")
        return generate_response("error", "Error registering camera"), 500
    

@app.route(f"{BASE_URL_PREFIX}/update", methods=['PUT'])
@requires_authentication()
def update_camera():
    """
    Updates information for an existing camera.

    Endpoint: PUT /cameras/update

    Parameters:
    - camera_name (string): Name of the camera to be updated.
    - region (string, optional): New region information.
    - address (string, optional): New address information.
    - max_speed_limit (int, optional): New maximum speed limit.
    - camera_url (string, optional): New URL of the camera.
    - camera_url_params (string, optional): New parameters associated with the camera URL.
    - camera_username (string, optional): New username for camera authentication.
    - camera_password (string, optional): New password for camera authentication.

    Returns:
    - 200 OK: Camera information updated successfully. Returns the updated camera information.
    - 400 Bad Request: Missing camera_name parameter or other required data.
    - 404 Not Found: The specified camera does not exist.
    - 500 Internal Server Error: Error updating camera information.
    """
    try:
        logger.info("Received PUT request for updating camera information.")
        data = request.json
        camera_name = data.get("camera_name")

        if not camera_name:
            logger.warning("Missing camera_name parameter.")
            return generate_response("error", "Missing camera_name parameter"), 400

        logger.debug(f"Request data: camera_name={camera_name}")

        # Check if the camera exists
        existing_camera = db.cameras.find_one({"camera_name": camera_name})
        if not existing_camera:
            logger.warning("Camera not found.")
            return generate_response("error", "Camera not found"), 404

        # Update camera information
        updated_data = {key: data[key] for key in data.keys() if key != "camera_name" and key in existing_camera}

        # Perform the update in the database
        db.cameras.update_one({"camera_name": camera_name}, {"$set": updated_data})

        # Retrieve the updated camera information
        updated_camera_info = db.cameras.find_one({"camera_name": camera_name})

        logger.info("Camera information updated successfully.")
        return generate_response("success", "Camera information updated successfully", camera=updated_camera_info), 200

    except Exception as e:
        logger.error(f"Error in update_camera: {str(e)}")
        return generate_response("error", "Error updating camera information"), 500

@app.route(f"{BASE_URL_PREFIX}/<camera_id>/delete", methods=['DELETE'])
@requires_authentication()
def delete_camera(camera_id):
    """
    Deletes an existing camera.

    Endpoint: DELETE /cameras/<camera_id>/delete

    Parameters:
    - camera_id (string): Identifier of the camera to be deleted.

    Returns:
    - 200 OK: Camera deleted successfully.
    - 404 Not Found: The specified camera does not exist.
    - 409 Conflict: The camera is linked to a provisioning node and cannot be deleted.
    - 500 Internal Server Error: Error deleting camera.
    """
    try:
        logger.info("Received DELETE request for deleting a camera.")
        
        # Check if the camera exists
        existing_camera = db.cameras.find_one({"_id": ObjectId(camera_id)})
        if not existing_camera:
            logger.warning("Camera not found.")
            return generate_response("error", "Camera not found"), 404

        # Check if the camera is linked in the provisioning collection
        linked_provisioning = db.provisioning.find_one({"camera_id": camera_id})
        if linked_provisioning:
            logger.warning("Camera is linked to a provisioning node and cannot be deleted.")
            return generate_response("error", "Camera is linked to a provisioning node and cannot be deleted"), 409

        # Delete the camera
        db.cameras.delete_one({"_id": ObjectId(camera_id)})

        logger.info("Camera deleted successfully.")
        return generate_response("success", "Camera deleted successfully"), 200

    except Exception as e:
        logger.error(f"Error in delete_camera: {str(e)}")
        return generate_response("error", "Error deleting camera"), 500
    

@app.route(f"{BASE_URL_PREFIX}/<camera_id>/frames/list", methods=['GET'])
@requires_authentication()
def get_frames(camera_id):
    """
    Retrieves a list of frames for a specific camera within a specified time range. Optionally, frames can be filtered based on vehicles that exceeded the maximum speed.

    Endpoint: GET /cameras/<camera_id>/frames/list

    Parameters:
    - camera_id (string): Identifier of the camera.
    - start_time (string): Start timestamp for frame retrieval.
    - end_time (string): End timestamp for frame retrieval.
    - page (int, optional): Page number for pagination (default is 1).
    - page_size (int, optional): Number of frames per page (default is 10).
    - filter_exceeded_speed (string, optional): Filter frames based on vehicles that exceeded the maximum speed. Set to 'true' to include only frames with speeding vehicles.

    Returns:
    - 200 OK: Frames retrieved successfully. Returns the list of frames.
    - 400 Bad Request: Missing required query parameters.
    - 500 Internal Server Error: Error processing the request.
    """
    try:
        logger.info("Received GET request for frames list.")
        start_time = request.args.get('start_time')
        end_time = request.args.get('end_time')
        page = int(request.args.get('page', 1))  # Current page
        page_size = int(request.args.get('page_size', DEFAULT_PAGE_SIZE))  # Page size
        filter_exceeded_speed = request.args.get('filter_exceeded_speed')  # Optional parameter

        logger.debug(f"Request parameters: camera_id={camera_id}, start_time={start_time}, end_time={end_time}, page={page}, page_size={page_size}, filter_exceeded_speed={filter_exceeded_speed}")

        # Validate query parameters
        if not (camera_id and start_time and end_time):
            logger.warning("Missing required query parameters.")
            return generate_response("error", "Missing required query parameters"), 400

        start_time = datetime.fromisoformat(start_time)
        end_time = datetime.fromisoformat(end_time)

        query = {
            "camera_id": camera_id,
            "frame_timestamp": {"$gte": start_time, "$lte": end_time}
        }

        # Check if the filter_exceeded_speed parameter is present and set to true
        if filter_exceeded_speed == 'true':
            query["processed_frame.detected_vehicles.exceeded_max_speed"] = True

        frames = list(db.frames.find(query).skip((page - 1) * page_size).limit(page_size))

        logger.debug(f"Retrieved frames: {frames}")

        response_data = {"frames": frames}
        return generate_response("success", "Frames retrieved successfully", data=response_data), 200

    except Exception as e:
        logger.error(f"Error in get_frames: {str(e)}")
        return generate_response("error", "Error processing request"), 500

@app.route(f"{BASE_URL_PREFIX}/list", methods=['GET'])
@requires_authentication()
def list_cameras():
    """
    Retrieves the list of cameras available in the collection.

    Endpoint: GET /cameras/list

    Returns:
    - 200 OK: List of cameras retrieved successfully.
    - 500 Internal Server Error: Error retrieving the list of cameras.
    """
    try:
        logger.info("Received GET request for the list of cameras.")

        # Retrieve the list of cameras from the database
        cameras = list(db.cameras.find())

        logger.debug(f"Retrieved cameras: {cameras}")

        response_data = {"cameras": cameras}
        return generate_response("success", "List of cameras retrieved successfully", data=response_data), 200

    except Exception as e:
        logger.error(f"Error in list_cameras: {str(e)}")
        return generate_response("error", "Error retrieving the list of cameras"), 500

@app.route(f"{BASE_URL_PREFIX}/frames/save", methods=['POST'])
def save_frame():
    """
    Saves processed frames information to the database.

    Endpoint: POST /cameras/frames/save

    Parameters:
    - mac_address (string): MAC address of the camera.
    - camera_id (string): ID of the camera.
    - frame_timestamp (string): Timestamp of the frame.
    - processed_frame (string): JSON string containing processed frame information.

    Returns:
    - 200 OK: Frame processed successfully.
    - 400 Bad Request: Missing required data.
    - 500 Internal Server Error: Error processing frame.
    """
    try:
        logger.info("Received POST request for saving frames.")
        data = request.json
        mac_address = data.get("mac_address")
        camera_id = data.get("camera_id")
        timestamp = data.get("frame_timestamp")
        processed_frame = eval(data.get("processed_frame"))  # Use eval to convert string to dictionary

        if not (mac_address and camera_id and timestamp and processed_frame):
            logger.warning("Missing required data.")
            return generate_response("error", "Missing required data"), 400

        logger.debug(f"Request data: mac_address={mac_address}, camera id={camera_id}")

        # Find the camera in the database by its ID
        camera = db.cameras.find_one({"_id": ObjectId(camera_id)})

        # Validate camera_id in the collection of cameras
        if camera is None:
            logger.warning(f"Invalid camera_id: {camera_id}")
            return generate_response("error", "Invalid camera_id"), 400

        # Validate camera_id and mac_address in the collection of provisioning with status "enabled"
        if not _is_provisioning_enabled(mac_address, camera_id):
            logger.warning(f"Camera or provisioning not enabled for mac_address={mac_address}, camera_id={camera_id}")
            return generate_response("error", "Camera or provisioning not enabled"), 401

        max_speed_allowed = camera.get("max_speed_limit")
        processed_timestamp = datetime.now()

        # Save the images to MinIO and get the URLs
        processed_frame["annotated_frame_name"] = _save_image_to_minio(processed_frame["annotated_frame_base64"])
        processed_frame["original_frame_name"] = _save_image_to_minio(processed_frame["original_frame_base64"])

        # Process vehicles in the frame
        processed_frame_unique_vehicles = set()
        for vehicle in processed_frame["detected_vehicles"]:
            vehicle_id = vehicle.get("vehicle_id")
            if vehicle_id not in processed_frame_unique_vehicles:
                processed_frame_unique_vehicles.add(vehicle_id)
            vehicle["vehicle_frame_name"] = _save_image_to_minio(vehicle["vehicle_frame_base64"])
            vehicle_speed_info = vehicle.get("speed_info", {})
            vehicle_speed = vehicle_speed_info.get("kph") if isinstance(vehicle_speed_info, dict) else None
            # Ensure both vehicle_speed and max_speed_allowed are not None before comparison
            if vehicle_speed is not None and max_speed_allowed is not None:
                # Mark vehicles that exceed the maximum speed limit
                if vehicle_speed > max_speed_allowed:
                    vehicle["exceeded_max_speed"] = True

        # Remove base64 data to reduce payload size
        processed_frame.pop("annotated_frame_base64", None)
        processed_frame.pop("original_frame_base64", None)

        for vehicle in processed_frame["detected_vehicles"]:
            vehicle.pop("vehicle_frame_base64", None)

        # Insert processed frame data into the database
        db.frames.insert_one({
            "mac_address": mac_address,
            "camera_id": camera_id,
            "frame_timestamp": timestamp,
            "processed_timestamp": processed_timestamp,
            "processed_frame": processed_frame
        })

        # Update the number of vehicles detected for this camera
        db.cameras.update_one(
            {"_id": ObjectId(camera_id)},
            {"$inc": {"vehicles_detected": len(processed_frame_unique_vehicles)}}
        )

        logger.info("Frame processed successfully.")
        return generate_response("success", "Frame processed successfully"), 200

    except Exception as e:
        logger.error(f"Error in save_frame: {str(e)}")
        import traceback
        traceback.print_exc()
        return generate_response("error", "Error processing frame"), 500
    

@app.route(f"{BASE_URL_PREFIX}/frames/image/<image_id>", methods=['GET'])
def get_image(image_id):
    """
    Retrieves an image from MinIO using the provided image ID.

    Endpoint: GET /cameras/frames/image/<image_id>

    Parameters:
    - image_id (string): Identifier of the image.

    Returns:
    - Image file: Retrieved image from MinIO.
    - 404 Not Found: The specified image does not exist.
    - 500 Internal Server Error: Error retrieving the image.
    """
    try:
        logger.info(f"Received GET request for image with ID: {image_id}")

        # Initialize the MinIO client
        minio_client = Minio(MINIO_ENDPOINT, access_key=MINIO_ACCESS_KEY, secret_key=MINIO_SECRET_KEY, secure=False)

        # Check if the image exists in MinIO
        found = minio_client.stat_object(MINIO_BUCKET, image_id)
        if not found:
            logger.warning(f"Image with ID '{image_id}' not found in MinIO.")
            return generate_response("error", f"Image with ID '{image_id}' not found"), 404

        # Get the image data from MinIO
        image_data = minio_client.get_object(MINIO_BUCKET, image_id)
        image_bytes = image_data.read()

        # Return the image as a response
        return send_file(io.BytesIO(image_bytes), mimetype='image/jpeg')

    except Exception as e:
        logger.error(f"Error in get_image: {str(e)}")
        return generate_response("error", "Error retrieving the image"), 500


# Function to check if provisioning is enabled for a specific MAC address and camera
def _is_provisioning_enabled(mac_address, camera_id):
    # Find provisioning in the database by MAC address, camera ID, and enabled status
    provisioning = db.provisioning.find_one({
        "mac_address": mac_address,
        "camera_id": camera_id,
        "status": "enabled"
    })
    # Return True if provisioning is enabled, otherwise False
    return provisioning is not None

# Function to save an image to MinIO
def _save_image_to_minio(base64_data):
    # Check if base64_data is None or an empty string
    if not base64_data:
        logger.warning("Base64 data is empty or None.")
        return None
    try:
        # Decode the image's Base64 data
        image_data = base64.b64decode(base64_data)

        # Generate a unique object name in MinIO using UUID
        object_name = f"{uuid.uuid4()}.jpg"

        # Initialize the MinIO client
        minio_client = Minio(MINIO_ENDPOINT, access_key=MINIO_ACCESS_KEY, secret_key=MINIO_SECRET_KEY, secure=False)

        # Check if the MinIO bucket exists; create it if it doesn't exist
        bucket_exists = minio_client.bucket_exists(MINIO_BUCKET)
        if not bucket_exists:
            logger.info(f"Bucket '{MINIO_BUCKET}' does not exist; creating...")
            minio_client.make_bucket(MINIO_BUCKET)

        # Store the image in MinIO
        minio_client.put_object(MINIO_BUCKET, object_name, io.BytesIO(image_data), len(image_data))

        # Return the name of the object saved in MinIO
        return object_name

    except Exception as e:
        logger.error(f"Error saving image to MinIO: {str(e)}")
        return None


if __name__ == "__main__":
    # Start the Flask application
    app.run(host="0.0.0.0", port=5000)
