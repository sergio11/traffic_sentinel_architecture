from functools import wraps
from flask import request, jsonify
import os
import jwt

JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "secret_key")

def requires_authentication(required_role=None):
    def decorator(func):
        @wraps(func)
        def decorated(*args, **kwargs):
            token = request.headers.get('Authentication')
            if not token:
                return jsonify(message='Unauthorized: JWT token is missing'), 401
            try:
                payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=['HS256'])
                if required_role and payload['role'] != required_role:
                    return jsonify(message='Unauthorized: Insufficient role'), 401
                return func(*args, **kwargs)
            except jwt.ExpiredSignatureError:
                return jsonify(message='Unauthorized: Token has expired'), 401
            except jwt.InvalidTokenError:
                return jsonify(message='Unauthorized: Invalid token'), 401
        return decorated
    return decorator
