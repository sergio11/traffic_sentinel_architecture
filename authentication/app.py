from flask import Flask, request, jsonify
from cassandra.cluster import Cluster
import hashlib
import uuid

app = Flask(__name__)

# Conectar a la base de datos ScyllaDB
cluster = Cluster(['scylla_db'])
session = cluster.connect('auth_keyspace')

@app.route('/get_challenge', methods=['POST'])
def get_challenge():
    try:
        data = request.get_json()
        mac_address = data.get('mac_address')
        
        query = "SELECT password FROM users WHERE mac_address = %s"
        result = session.execute(query, (mac_address,))
        
        if result:
            stored_password = result[0].password
            challenge = str(uuid.uuid4())  # Generar un reto único
            response = hashlib.sha256((stored_password + challenge).encode()).hexdigest()
            return jsonify(challenge=challenge, response=response), 200
        else:
            return jsonify(message='MAC address not found'), 404
    except Exception as e:
        return jsonify(message=str(e)), 500

@app.route('/authenticate', methods=['POST'])
def authenticate():
    try:
        data = request.get_json()
        mac_address = data.get('mac_address')
        client_response = data.get('client_response')
        
        query = "SELECT password, challenge FROM users WHERE mac_address = %s"
        result = session.execute(query, (mac_address,))
        
        if result:
            stored_password = result[0].password
            stored_challenge = result[0].challenge
            expected_response = hashlib.sha256((stored_password + stored_challenge).encode()).hexdigest()
            
            if client_response == expected_response:
                return jsonify(message='Authentication successful'), 200
            else:
                return jsonify(message='Authentication failed'), 401
        else:
            return jsonify(message='MAC address not found'), 404
    except Exception as e:
        return jsonify(message=str(e)), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
