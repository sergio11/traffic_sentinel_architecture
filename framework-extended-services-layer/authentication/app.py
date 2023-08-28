from flask import Flask, request, jsonify
import hashlib
import uuid
import requests
import os
import redis

def get_vault_token():
    try:
        token = redis_client.get("vault_root_token")
        if token:
            return token.decode("utf-8")
        else:
            raise Exception("Vault token not found in Redis")
    except Exception as e:
        raise Exception("Error retrieving Vault token from Redis")
    
def get_stored_password(mac_address):
    try:
        response = requests.get(
            f"{VAULT_ADDRESS}/v1/secret/data/users/{mac_address}",
            headers={"X-Vault-Token": VAULT_TOKEN}
        )
        response_json = response.json()
        stored_password = response_json["data"]["password"]
        return stored_password
    except Exception as e:
        raise Exception("Error retrieving stored password from Vault")

def get_code_hash(mac_address):
    try:
        response = requests.get(
            f"{VAULT_ADDRESS}/v1/secret/data/fog_nodes/{mac_address}",
            headers={"X-Vault-Token": VAULT_TOKEN}
        )
        response_json = response.json()
        code_hash = response_json["data"]["code_hash"]
        return code_hash
    except Exception as e:
        raise Exception("Error retrieving code hash from Vault")
    
app = Flask(__name__)

# Redis Configuration
REDIS_HOST = os.environ.get("REDIS_HOST", "redis")
REDIS_PORT = int(os.environ.get("REDIS_PORT", 6379))
redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0)
# Vault Configuration
VAULT_ADDRESS = os.environ.get("VAULT_ADDRESS", "http://vault:8200")
VAULT_TOKEN = get_vault_token()

@app.route('/get_challenge', methods=['POST'])
def get_challenge():
    try:
        data = request.get_json()
        mac_address = data.get('mac_address')
        
        stored_password = get_stored_password(mac_address)
        code_hash = get_code_hash(mac_address)

        challenge = str(uuid.uuid4())  # Generate challenge

        # Store the CHAP challenge result in Redis with a 2-minute expiration
        redis_key = f"{mac_address}_challenge"
        redis_client.set(redis_key, hashlib.sha256((stored_password + challenge + code_hash).encode()).hexdigest(), ex=120)
        
        # Log the challenge and generated UUID
        print(f"Challenge generated for MAC {mac_address}: {challenge}")

        return jsonify(challenge=challenge), 200
    except Exception as e:
        return jsonify(message=str(e)), 500

@app.route('/authenticate', methods=['POST'])
def authenticate():
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
                return jsonify(message='Authentication successful', session_id=session_uuid), 200
            else:
                return jsonify(message='Authentication failed'), 401
        else:
            return jsonify(message='Challenge not found'), 404
    except Exception as e:
        return jsonify(message=str(e)), 500
    



if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
