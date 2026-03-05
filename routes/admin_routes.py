from flask import Blueprint, request, jsonify
from datetime import datetime
from config.db import get_db
from models.user import serialize_user
from middleware.auth import role_required, get_current_user

admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/users', methods=['GET'])
@role_required('admin')
def get_all_users():
    try:
        db = get_db()
        role = request.args.get('role')
        
        query = {}
        if role:
            query['role'] = role
        
        users = list(db.users.find(query).sort('created_at', -1))
        return jsonify({"users": [serialize_user(u) for u in users]}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@admin_bp.route('/users/<user_id>/approve', methods=['PUT'])
@role_required('admin')
def approve_instructor(user_id):
    try:
        db = get_db()
        user = db.users.find_one({"user_id": user_id})
        if not user:
            return jsonify({"error": "User not found"}), 404
        
        db.users.update_one(
            {"user_id": user_id},
            {"$set": {"is_approved": True, "updated_at": datetime.utcnow()}}
        )
        return jsonify({"message": "User approved"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@admin_bp.route('/users/<user_id>/revoke', methods=['PUT'])
@role_required('admin')
def revoke_access(user_id):
    try:
        db = get_db()
        user = db.users.find_one({"user_id": user_id})
        if not user:
            return jsonify({"error": "User not found"}), 404
        if user.get('role') == 'admin':
            return jsonify({"error": "Cannot revoke admin access"}), 403
        
        db.users.update_one(
            {"user_id": user_id},
            {"$set": {"is_approved": False, "is_active": False, "updated_at": datetime.utcnow()}}
        )
        return jsonify({"message": "Access revoked"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@admin_bp.route('/users/<user_id>/activate', methods=['PUT'])
@role_required('admin')
def activate_user(user_id):
    try:
        db = get_db()
        db.users.update_one(
            {"user_id": user_id},
            {"$set": {"is_active": True, "is_approved": True, "updated_at": datetime.utcnow()}}
        )
        return jsonify({"message": "User activated"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@admin_bp.route('/stats', methods=['GET'])
@role_required('admin')
def get_stats():
    try:
        db = get_db()
        total_users = db.users.count_documents({})
        total_students = db.users.count_documents({"role": "student"})
        total_instructors = db.users.count_documents({"role": "instructor"})
        pending_instructors = db.users.count_documents({"role": "instructor", "is_approved": False})
        total_courses = db.courses.count_documents({})
        published_courses = db.courses.count_documents({"is_published": True})
        
        return jsonify({
            "stats": {
                "total_users": total_users,
                "total_students": total_students,
                "total_instructors": total_instructors,
                "pending_instructors": pending_instructors,
                "total_courses": total_courses,
                "published_courses": published_courses
            }
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@admin_bp.route('/courses', methods=['GET'])
@role_required('admin')
def get_all_courses():
    try:
        db = get_db()
        from models.course import serialize_course
        courses = list(db.courses.find().sort('created_at', -1))
        result = []
        for course in courses:
            c = serialize_course(course)
            instructor = db.users.find_one({"user_id": course['instructor_id']})
            c['instructor_name'] = instructor['full_name'] if instructor else "Unknown"
            result.append(c)
        return jsonify({"courses": result}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
