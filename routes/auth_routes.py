from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token, get_jwt_identity
from datetime import datetime, timedelta
from config.db import get_db
from models.user import create_user, get_user_by_email, verify_password, serialize_user, update_user
from middleware.auth import token_required, get_current_user

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/register', methods=['POST'])
def register():
    try:
        db = get_db()
        data = request.get_json()
        
        required = ['email', 'password', 'full_name', 'role']
        for field in required:
            if not data.get(field):
                return jsonify({"error": f"{field} is required"}), 400
        
        role = data.get('role', 'student')
        if role not in ['student', 'instructor']:
            return jsonify({"error": "Invalid role"}), 400
        
        if get_user_by_email(db, data['email']):
            return jsonify({"error": "Email already registered"}), 409
        
        if len(data['password']) < 6:
            return jsonify({"error": "Password must be at least 6 characters"}), 400
        
        user = create_user(db, data['email'], data['password'], data['full_name'], role)
        
        message = "Account created successfully"
        if role == 'instructor':
            message = "Account created. Awaiting admin approval."
        
        return jsonify({
            "message": message,
            "user": serialize_user(user)
        }), 201
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@auth_bp.route('/login', methods=['POST'])
def login():
    try:
        db = get_db()
        data = request.get_json()
        
        if not data.get('email') or not data.get('password'):
            return jsonify({"error": "Email and password required"}), 400
        
        user = get_user_by_email(db, data['email'])
        if not user or not verify_password(data['password'], user['password']):
            return jsonify({"error": "Invalid credentials"}), 401
        
        if not user.get('is_active', True):
            return jsonify({"error": "Account has been deactivated"}), 403
        
        if not user.get('is_approved', False):
            return jsonify({"error": "Account pending admin approval"}), 403
        
        db.users.update_one(
            {"user_id": user['user_id']},
            {"$set": {"last_login": datetime.utcnow()}}
        )
        
        token = create_access_token(
            identity=user['user_id'],
            expires_delta=timedelta(days=7)
        )
        
        return jsonify({
            "token": token,
            "user": serialize_user(user)
        }), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@auth_bp.route('/me', methods=['GET'])
@token_required
def get_me():
    try:
        user = get_current_user()
        if not user:
            return jsonify({"error": "User not found"}), 404
        return jsonify({"user": serialize_user(user)}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@auth_bp.route('/update-profile', methods=['PUT'])
@token_required
def update_profile():
    try:
        user = get_current_user()
        if not user:
            return jsonify({"error": "User not found"}), 404
        
        db = get_db()
        data = request.get_json()
        
        allowed = ['full_name', 'bio', 'phone', 'website', 'social_links']
        update_data = {k: v for k, v in data.items() if k in allowed}
        
        updated = update_user(db, user['user_id'], update_data)
        return jsonify({"user": serialize_user(updated), "message": "Profile updated"}), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@auth_bp.route('/upload-avatar', methods=['POST'])
@token_required
def upload_avatar():
    try:
        from config.cloudinary_config import upload_image
        user = get_current_user()
        if not user:
            return jsonify({"error": "User not found"}), 404
        
        if 'avatar' not in request.files:
            return jsonify({"error": "No file provided"}), 400
        
        file = request.files['avatar']
        result = upload_image(file, folder="lms/avatars")
        
        db = get_db()
        db.users.update_one(
            {"user_id": user['user_id']},
            {"$set": {"avatar": result['url'], "updated_at": datetime.utcnow()}}
        )
        
        return jsonify({"avatar": result['url'], "message": "Avatar updated"}), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@auth_bp.route('/change-password', methods=['PUT'])
@token_required
def change_password():
    try:
        from models.user import hash_password
        user = get_current_user()
        db = get_db()
        data = request.get_json()
        
        if not verify_password(data.get('current_password', ''), user['password']):
            return jsonify({"error": "Current password is incorrect"}), 400
        
        if len(data.get('new_password', '')) < 6:
            return jsonify({"error": "New password must be at least 6 characters"}), 400
        
        db.users.update_one(
            {"user_id": user['user_id']},
            {"$set": {"password": hash_password(data['new_password']), "updated_at": datetime.utcnow()}}
        )
        
        return jsonify({"message": "Password changed successfully"}), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500
