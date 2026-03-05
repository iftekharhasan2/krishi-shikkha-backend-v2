from datetime import datetime
import bcrypt
import uuid

def hash_password(password):
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(password, hashed):
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

def create_user(db, email, password, full_name, role="student"):
    user = {
        "user_id": str(uuid.uuid4())[:8].upper(),
        "email": email.lower().strip(),
        "password": hash_password(password),
        "full_name": full_name,
        "role": role,  # student | instructor | admin
        "is_approved": role == "student" or role == "admin",
        "avatar": None,
        "bio": "",
        "phone": "",
        "website": "",
        "social_links": {"twitter": "", "linkedin": "", "github": ""},
        "enrolled_courses": [],
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
        "last_login": None,
        "is_active": True
    }
    result = db.users.insert_one(user)
    user["_id"] = str(result.inserted_id)
    return user

def get_user_by_email(db, email):
    return db.users.find_one({"email": email.lower().strip()})

def get_user_by_id(db, user_id):
    return db.users.find_one({"user_id": user_id})

def update_user(db, user_id, update_data):
    update_data["updated_at"] = datetime.utcnow()
    db.users.update_one({"user_id": user_id}, {"$set": update_data})
    return db.users.find_one({"user_id": user_id})

def serialize_user(user):
    if not user:
        return None
    return {
        "id": str(user.get("_id", "")),
        "user_id": user.get("user_id"),
        "email": user.get("email"),
        "full_name": user.get("full_name"),
        "role": user.get("role"),
        "is_approved": user.get("is_approved", False),
        "avatar": user.get("avatar"),
        "bio": user.get("bio", ""),
        "phone": user.get("phone", ""),
        "website": user.get("website", ""),
        "social_links": user.get("social_links", {}),
        "enrolled_courses": user.get("enrolled_courses", []),
        "created_at": user.get("created_at", "").isoformat() if user.get("created_at") else "",
        "is_active": user.get("is_active", True)
    }
