from datetime import datetime
import uuid

def create_course(db, instructor_id, data):
    course = {
        "course_id": str(uuid.uuid4())[:12].upper(),
        "title": data.get("title"),
        "description": data.get("description", ""),
        "short_description": data.get("short_description", ""),
        "instructor_id": instructor_id,
        "price": float(data.get("price", 0)),
        "category": data.get("category", "General"),
        "level": data.get("level", "Beginner"),
        "tags": data.get("tags", []),
        "thumbnail": data.get("thumbnail"),
        "thumbnail_public_id": data.get("thumbnail_public_id"),
        "sections": [],
        "enrolled_students": [],
        "total_students": 0,
        "total_lessons": 0,
        "total_duration": 0,
        "rating": 0,
        "reviews": [],
        "is_published": False,
        "language": data.get("language", "English"),
        "requirements": data.get("requirements", []),
        "what_you_learn": data.get("what_you_learn", []),
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
    result = db.courses.insert_one(course)
    course["_id"] = str(result.inserted_id)
    return course

def serialize_course(course, include_sections=False):
    if not course:
        return None
    data = {
        "id": str(course.get("_id", "")),
        "course_id": course.get("course_id"),
        "title": course.get("title"),
        "description": course.get("description", ""),
        "short_description": course.get("short_description", ""),
        "instructor_id": course.get("instructor_id"),
        "price": course.get("price", 0),
        "category": course.get("category"),
        "level": course.get("level"),
        "tags": course.get("tags", []),
        "thumbnail": course.get("thumbnail"),
        "total_students": course.get("total_students", 0),
        "total_lessons": course.get("total_lessons", 0),
        "total_duration": course.get("total_duration", 0),
        "rating": course.get("rating", 0),
        "reviews_count": len(course.get("reviews", [])),
        "is_published": course.get("is_published", False),
        "language": course.get("language", "English"),
        "requirements": course.get("requirements", []),
        "what_you_learn": course.get("what_you_learn", []),
        "created_at": course.get("created_at", "").isoformat() if course.get("created_at") else ""
    }
    if include_sections:
        data["sections"] = course.get("sections", [])
        data["enrolled_students"] = course.get("enrolled_students", [])
    return data
