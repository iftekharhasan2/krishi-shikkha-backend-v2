from functools import wraps
from flask import jsonify
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity
from config.db import get_db

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        try:
            verify_jwt_in_request()
            return f(*args, **kwargs)
        except Exception as e:
            return jsonify({"error": "Invalid or expired token"}), 401
    return decorated

def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            try:
                verify_jwt_in_request()
                identity = get_jwt_identity()
                db = get_db()
                user = db.users.find_one({"user_id": identity})
                if not user:
                    return jsonify({"error": "User not found"}), 404
                if user.get("role") not in roles:
                    return jsonify({"error": "Insufficient permissions"}), 403
                if not user.get("is_approved", False):
                    return jsonify({"error": "Account pending approval"}), 403
                return f(*args, **kwargs)
            except Exception as e:
                return jsonify({"error": str(e)}), 401
        return decorated
    return decorator

def get_current_user():
    try:
        verify_jwt_in_request()
        identity = get_jwt_identity()
        db = get_db()
        return db.users.find_one({"user_id": identity})
    except:
        return None
