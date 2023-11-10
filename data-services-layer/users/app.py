import logging

from common.helpers import generate_response
from common.requires_authentication_decorator import requires_authentication
from flask import Flask, request, jsonify
import hashlib
import os
import jwt
from pymongo import MongoClient, DESCENDING

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Flask(__name__)

BASE_URL_PREFIX = "/users"

JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "secret_key")
# MongoDB Configuration
MONGO_CONNECTION_URL = os.environ.get("MONGO_CONNECTION_URL", "mongodb://localhost:27017/")
MONGO_DB = os.environ.get("MONGO_DB", "db")
mongo_client = MongoClient(MONGO_CONNECTION_URL)
db = mongo_client[MONGO_DB]


# Endpoint to register new users (only administrators can do this)
@app.route(f"{BASE_URL_PREFIX}/register", methods=['POST'])
@requires_authentication(required_role="admin")
def register_user():
    try:
        data = request.get_json()
        role = data.get('role')
        username = data.get('username')
        password = data.get('password')

        # Check if the role is valid (either "operator" or "admin")
        if role not in ("operator", "admin"):
            return generate_response("error", "Invalid role"), 400

        # Check if username and password are not empty
        if not username or not password:
            return generate_response("error", "Username and password are required"), 400

        # Check if the user already exists
        existing_user = db.users.find_one({"username": username})

        if existing_user:
            return generate_response("error", "User already exists"), 400

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
            return generate_response("success", "User registered successfully")
        else:
            return generate_response("error", "User registration failed"), 500

    except Exception as e:
        return generate_response("error", str(e)), 500

# Endpoint to authenticate users
@app.route(f"{BASE_URL_PREFIX}/authenticate", methods=['POST'])
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
                    return generate_response("success", "Authentication successful", session_token=session_token), 200
                else:
                    return generate_response("error", "Authentication failed: User is not enabled"), 401
            else:
                return generate_response("error", "Authentication failed: Invalid credentials"), 401
        else:
            return generate_response("error", "Authentication failed: User not found"), 404

    except Exception as e:
        return generate_response("error", str(e)), 500


# Endpoint to enable/disable users (only administrators can do this)
@app.route(f"{BASE_URL_PREFIX}/toggle-status", methods=['POST'])
@requires_authentication(required_role="admin")
def toggle_user_status():
    try:
        data = request.get_json()
        username = data.get('username')
        status = data.get('status')  # 'enable' or 'disable'

        if status not in ('enable', 'disable'):
            return generate_response("error", "Invalid status"), 400

        # Update user status in the database
        db.users.update_one({"username": username}, {"$set": {"enabled": status == 'enable'}})

        return generate_response("success", f"User {username} {status}d successfully"), 200
    except Exception as e:
        return generate_response("error", str(e)), 500

# Endpoint to list all registered users with pagination and sorting
@app.route(f"{BASE_URL_PREFIX}/list", methods=['GET'])
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
        return generate_response("success", "Users listed successfully", users=users), 200
    except Exception as e:
        return generate_response("error", str(e)), 500


@app.route(f"{BASE_URL_PREFIX}/check-admin", methods=["GET"])
def check_admin_user():
    """
    Check the existence of the admin user and create it if it does not exist.

    Returns:
    - 200 OK: If the admin user exists.
    - 201 Created: If the admin user is created successfully.
    - 500 Internal Server Error: If an error occurs during the process.
    """
    try:
        admin_username = os.environ.get("ADMIN_USERNAME", "admin")
        admin_user = db.users.find_one({"username": admin_username, "role": "admin"})

        if admin_user:
            return generate_response("success", "Admin user exists.")
        else:
            _create_admin_user()
            return generate_response("success", "Admin user created successfully."), 201

    except Exception as e:
        return generate_response("error", str(e)), 500


def _create_admin_user():
    # Environment variables
    admin_username = os.environ.get("ADMIN_USERNAME", "admin")
    admin_password = os.environ.get("ADMIN_PASSWORD", "admin_password")

    # Check if the admin user already exists
    existing_admin_user = db.users.find_one({"username": admin_username, "role": "admin"})

    if not existing_admin_user:
        # Hash the password
        hashed_password = hashlib.sha256(admin_password.encode()).hexdigest()

        # Create the admin user
        admin_user = {
            "username": admin_username,
            "password": hashed_password,
            "role": "admin",
            "enabled": True  # Enable the user by default
        }

        # Insert the admin user into the MongoDB collection
        db.users.insert_one(admin_user)
        logger.info("Admin user created successfully.")
    else:
        logger.info("The admin user already exists.")


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
