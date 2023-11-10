from flask import jsonify

def generate_response(status, message, **kwargs):
    response = {"status": status, "message": message}
    response.update(kwargs)
    return jsonify(response)