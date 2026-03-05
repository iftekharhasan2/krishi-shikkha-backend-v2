from flask import Blueprint, request, jsonify
from flask_jwt_extended import get_jwt_identity
from datetime import datetime
import uuid
from config.db import get_db
from config.cloudinary_config import upload_image, upload_video, upload_file, delete_resource
from models.course import create_course, serialize_course
from middleware.auth import token_required, role_required, get_current_user

course_bp = Blueprint('courses', __name__)

@course_bp.route('/', methods=['GET'])
def get_courses():
    try:
        db = get_db()
        query = {"is_published": True}
        
        category = request.args.get('category')
        level = request.args.get('level')
        search = request.args.get('search')
        
        if category:
            query['category'] = category
        if level:
            query['level'] = level
        if search:
            query['$or'] = [
                {'title': {'$regex': search, '$options': 'i'}},
                {'description': {'$regex': search, '$options': 'i'}},
                {'tags': {'$in': [search.lower()]}}
            ]
        
        courses = list(db.courses.find(query).sort('created_at', -1))
        
        result = []
        for course in courses:
            c = serialize_course(course)
            instructor = db.users.find_one({"user_id": course['instructor_id']})
            c['instructor_name'] = instructor['full_name'] if instructor else "Unknown"
            c['instructor_avatar'] = instructor.get('avatar') if instructor else None
            result.append(c)
        
        return jsonify({"courses": result}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@course_bp.route('/<course_id>', methods=['GET'])
def get_course(course_id):
    try:
        db = get_db()
        course = db.courses.find_one({"course_id": course_id})
        if not course:
            return jsonify({"error": "Course not found"}), 404
        
        current_user = get_current_user()
        is_enrolled = False
        is_instructor = False
        
        if current_user:
            is_enrolled = course_id in [c for c in current_user.get('enrolled_courses', [])]
            is_instructor = current_user['user_id'] == course['instructor_id'] or current_user['role'] == 'admin'
        
        c = serialize_course(course, include_sections=True)
        instructor = db.users.find_one({"user_id": course['instructor_id']})
        c['instructor_name'] = instructor['full_name'] if instructor else "Unknown"
        c['instructor_bio'] = instructor.get('bio', '') if instructor else ""
        c['instructor_avatar'] = instructor.get('avatar') if instructor else None
        c['is_enrolled'] = is_enrolled
        c['is_instructor'] = is_instructor
        
        # Hide video URLs for non-enrolled, non-instructor (except first lesson)
        if not is_enrolled and not is_instructor:
            for section in c.get('sections', []):
                for i, lesson in enumerate(section.get('lessons', [])):
                    if not lesson.get('is_free', False):
                        lesson['video_url'] = None
                        lesson['notes'] = []
        
        return jsonify({"course": c}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@course_bp.route('/', methods=['POST'])
@role_required('instructor', 'admin')
def create_new_course():
    try:
        db = get_db()
        current_user = get_current_user()
        data = request.get_json()
        
        if not data.get('title'):
            return jsonify({"error": "Course title is required"}), 400
        
        course = create_course(db, current_user['user_id'], data)
        return jsonify({"course": serialize_course(course), "message": "Course created"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@course_bp.route('/<course_id>', methods=['PUT'])
@role_required('instructor', 'admin')
def update_course(course_id):
    try:
        db = get_db()
        current_user = get_current_user()
        course = db.courses.find_one({"course_id": course_id})
        
        if not course:
            return jsonify({"error": "Course not found"}), 404
        if course['instructor_id'] != current_user['user_id'] and current_user['role'] != 'admin':
            return jsonify({"error": "Not authorized"}), 403
        
        data = request.get_json()
        allowed = ['title', 'description', 'short_description', 'price', 'category', 
                   'level', 'tags', 'language', 'requirements', 'what_you_learn', 'is_published']
        update_data = {k: v for k, v in data.items() if k in allowed}
        update_data['updated_at'] = datetime.utcnow()
        
        db.courses.update_one({"course_id": course_id}, {"$set": update_data})
        updated = db.courses.find_one({"course_id": course_id})
        return jsonify({"course": serialize_course(updated), "message": "Course updated"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@course_bp.route('/<course_id>/thumbnail', methods=['POST'])
@role_required('instructor', 'admin')
def upload_thumbnail(course_id):
    try:
        db = get_db()
        current_user = get_current_user()
        course = db.courses.find_one({"course_id": course_id})
        
        if not course:
            return jsonify({"error": "Course not found"}), 404
        if course['instructor_id'] != current_user['user_id'] and current_user['role'] != 'admin':
            return jsonify({"error": "Not authorized"}), 403
        
        if 'thumbnail' not in request.files:
            return jsonify({"error": "No file provided"}), 400
        
        file = request.files['thumbnail']
        result = upload_image(file, folder=f"lms/courses/{course_id}")
        
        db.courses.update_one(
            {"course_id": course_id},
            {"$set": {"thumbnail": result['url'], "thumbnail_public_id": result['public_id'], "updated_at": datetime.utcnow()}}
        )
        
        return jsonify({"thumbnail": result['url']}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ---- SECTIONS ----

@course_bp.route('/<course_id>/sections', methods=['POST'])
@role_required('instructor', 'admin')
def add_section(course_id):
    try:
        db = get_db()
        current_user = get_current_user()
        course = db.courses.find_one({"course_id": course_id})
        
        if not course:
            return jsonify({"error": "Course not found"}), 404
        if course['instructor_id'] != current_user['user_id'] and current_user['role'] != 'admin':
            return jsonify({"error": "Not authorized"}), 403
        
        data = request.get_json()
        section = {
            "section_id": str(uuid.uuid4())[:8],
            "title": data.get('title', 'New Section'),
            "description": data.get('description', ''),
            "lessons": [],
            "order": len(course.get('sections', []))
        }
        
        db.courses.update_one(
            {"course_id": course_id},
            {"$push": {"sections": section}, "$set": {"updated_at": datetime.utcnow()}}
        )
        
        return jsonify({"section": section, "message": "Section added"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@course_bp.route('/<course_id>/sections/<section_id>', methods=['PUT'])
@role_required('instructor', 'admin')
def update_section(course_id, section_id):
    try:
        db = get_db()
        current_user = get_current_user()
        course = db.courses.find_one({"course_id": course_id})
        
        if not course:
            return jsonify({"error": "Course not found"}), 404
        if course['instructor_id'] != current_user['user_id'] and current_user['role'] != 'admin':
            return jsonify({"error": "Not authorized"}), 403
        
        data = request.get_json()
        db.courses.update_one(
            {"course_id": course_id, "sections.section_id": section_id},
            {"$set": {
                "sections.$.title": data.get('title'),
                "sections.$.description": data.get('description', ''),
                "updated_at": datetime.utcnow()
            }}
        )
        
        return jsonify({"message": "Section updated"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ---- LESSONS ----

@course_bp.route('/<course_id>/sections/<section_id>/lessons', methods=['POST'])
@role_required('instructor', 'admin')
def add_lesson(course_id, section_id):
    try:
        db = get_db()
        current_user = get_current_user()
        course = db.courses.find_one({"course_id": course_id})
        
        if not course:
            return jsonify({"error": "Course not found"}), 404
        if course['instructor_id'] != current_user['user_id'] and current_user['role'] != 'admin':
            return jsonify({"error": "Not authorized"}), 403
        
        # Find the section and count existing lessons to determine if first
        all_lessons_count = sum(len(s.get('lessons', [])) for s in course.get('sections', []))
        
        lesson = {
            "lesson_id": str(uuid.uuid4())[:8],
            "title": request.form.get('title', 'New Lesson'),
            "description": request.form.get('description', ''),
            "video_url": None,
            "video_public_id": None,
            "duration": 0,
            "notes": [],
            "is_free": all_lessons_count == 0,  # First lesson is always free
            "order": 0,
            "created_at": datetime.utcnow().isoformat()
        }
        
        # Upload video if provided
        if 'video' in request.files:
            video_file = request.files['video']
            video_result = upload_video(video_file, folder=f"lms/courses/{course_id}/videos")
            lesson['video_url'] = video_result['url']
            lesson['video_public_id'] = video_result['public_id']
            lesson['duration'] = video_result.get('duration', 0)
        
        # Upload notes if provided
        if 'notes' in request.files:
            notes_files = request.files.getlist('notes')
            for note_file in notes_files:
                note_result = upload_file(note_file, folder=f"lms/courses/{course_id}/notes")
                lesson['notes'].append({
                    "note_id": str(uuid.uuid4())[:8],
                    "name": note_file.filename,
                    "url": note_result['url'],
                    "public_id": note_result['public_id'],
                    "size": note_result.get('bytes', 0),
                    "format": note_result.get('format', '')
                })
        
        # Add lesson to section
        db.courses.update_one(
            {"course_id": course_id, "sections.section_id": section_id},
            {"$push": {"sections.$.lessons": lesson}}
        )
        
        # Update course stats
        _update_course_stats(db, course_id)
        
        return jsonify({"lesson": lesson, "message": "Lesson added"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@course_bp.route('/<course_id>/sections/<section_id>/lessons/<lesson_id>', methods=['PUT'])
@role_required('instructor', 'admin')
def update_lesson(course_id, section_id, lesson_id):
    try:
        db = get_db()
        current_user = get_current_user()
        course = db.courses.find_one({"course_id": course_id})
        
        if not course:
            return jsonify({"error": "Course not found"}), 404
        if course['instructor_id'] != current_user['user_id'] and current_user['role'] != 'admin':
            return jsonify({"error": "Not authorized"}), 403
        
        # Find section and lesson
        section_idx = None
        lesson_idx = None
        for si, s in enumerate(course.get('sections', [])):
            if s['section_id'] == section_id:
                section_idx = si
                for li, l in enumerate(s.get('lessons', [])):
                    if l['lesson_id'] == lesson_id:
                        lesson_idx = li
                        break
                break
        
        if section_idx is None or lesson_idx is None:
            return jsonify({"error": "Lesson not found"}), 404
        
        lesson = course['sections'][section_idx]['lessons'][lesson_idx]
        
        # Update text fields
        title = request.form.get('title')
        description = request.form.get('description')
        if title:
            lesson['title'] = title
        if description is not None:
            lesson['description'] = description
        
        # Upload new video if provided
        if 'video' in request.files:
            video_file = request.files['video']
            if lesson.get('video_public_id'):
                delete_resource(lesson['video_public_id'], 'video')
            video_result = upload_video(video_file, folder=f"lms/courses/{course_id}/videos")
            lesson['video_url'] = video_result['url']
            lesson['video_public_id'] = video_result['public_id']
            lesson['duration'] = video_result.get('duration', 0)
        
        # Add new notes
        if 'notes' in request.files:
            notes_files = request.files.getlist('notes')
            for note_file in notes_files:
                note_result = upload_file(note_file, folder=f"lms/courses/{course_id}/notes")
                if 'notes' not in lesson:
                    lesson['notes'] = []
                lesson['notes'].append({
                    "note_id": str(uuid.uuid4())[:8],
                    "name": note_file.filename,
                    "url": note_result['url'],
                    "public_id": note_result['public_id'],
                    "size": note_result.get('bytes', 0),
                    "format": note_result.get('format', '')
                })
        
        lesson['updated_at'] = datetime.utcnow().isoformat()
        
        # Update in DB
        db.courses.update_one(
            {"course_id": course_id},
            {"$set": {
                f"sections.{section_idx}.lessons.{lesson_idx}": lesson,
                "updated_at": datetime.utcnow()
            }}
        )
        
        _update_course_stats(db, course_id)
        return jsonify({"lesson": lesson, "message": "Lesson updated"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@course_bp.route('/<course_id>/sections/<section_id>/lessons/<lesson_id>/notes/<note_id>', methods=['DELETE'])
@role_required('instructor', 'admin')
def delete_note(course_id, section_id, lesson_id, note_id):
    try:
        db = get_db()
        current_user = get_current_user()
        course = db.courses.find_one({"course_id": course_id})
        
        if not course:
            return jsonify({"error": "Course not found"}), 404
        if course['instructor_id'] != current_user['user_id'] and current_user['role'] != 'admin':
            return jsonify({"error": "Not authorized"}), 403
        
        for si, s in enumerate(course.get('sections', [])):
            if s['section_id'] == section_id:
                for li, l in enumerate(s.get('lessons', [])):
                    if l['lesson_id'] == lesson_id:
                        notes = l.get('notes', [])
                        note = next((n for n in notes if n['note_id'] == note_id), None)
                        if note:
                            delete_resource(note['public_id'], 'raw')
                            updated_notes = [n for n in notes if n['note_id'] != note_id]
                            db.courses.update_one(
                                {"course_id": course_id},
                                {"$set": {f"sections.{si}.lessons.{li}.notes": updated_notes}}
                            )
        
        return jsonify({"message": "Note deleted"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ---- ENROLLMENT ----

@course_bp.route('/<course_id>/enroll', methods=['POST'])
@role_required('student', 'admin')
def enroll_course(course_id):
    try:
        db = get_db()
        current_user = get_current_user()
        course = db.courses.find_one({"course_id": course_id})
        
        if not course:
            return jsonify({"error": "Course not found"}), 404
        if not course.get('is_published'):
            return jsonify({"error": "Course is not available"}), 400
        
        if course_id in current_user.get('enrolled_courses', []):
            return jsonify({"error": "Already enrolled"}), 409
        
        enrollment = {
            "user_id": current_user['user_id'],
            "enrolled_at": datetime.utcnow().isoformat(),
            "progress": 0,
            "completed_lessons": []
        }
        
        db.courses.update_one(
            {"course_id": course_id},
            {
                "$push": {"enrolled_students": enrollment},
                "$inc": {"total_students": 1},
                "$set": {"updated_at": datetime.utcnow()}
            }
        )
        
        db.users.update_one(
            {"user_id": current_user['user_id']},
            {"$push": {"enrolled_courses": course_id}}
        )
        
        return jsonify({"message": "Enrolled successfully"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@course_bp.route('/<course_id>/progress', methods=['POST'])
@token_required
def update_progress(course_id):
    try:
        db = get_db()
        current_user = get_current_user()
        data = request.get_json()
        lesson_id = data.get('lesson_id')
        
        course = db.courses.find_one({"course_id": course_id})
        if not course:
            return jsonify({"error": "Course not found"}), 404
        
        # Update completed lessons for this student
        for i, student in enumerate(course.get('enrolled_students', [])):
            if student['user_id'] == current_user['user_id']:
                completed = student.get('completed_lessons', [])
                if lesson_id not in completed:
                    completed.append(lesson_id)
                
                total = course.get('total_lessons', 1)
                progress = round((len(completed) / total) * 100) if total > 0 else 0
                
                db.courses.update_one(
                    {"course_id": course_id, "enrolled_students.user_id": current_user['user_id']},
                    {"$set": {
                        "enrolled_students.$.completed_lessons": completed,
                        "enrolled_students.$.progress": progress
                    }}
                )
                return jsonify({"progress": progress}), 200
        
        return jsonify({"error": "Not enrolled"}), 403
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@course_bp.route('/my/enrolled', methods=['GET'])
@token_required
def my_courses():
    try:
        db = get_db()
        current_user = get_current_user()
        enrolled_ids = current_user.get('enrolled_courses', [])
        
        courses = []
        for cid in enrolled_ids:
            course = db.courses.find_one({"course_id": cid})
            if course:
                c = serialize_course(course)
                # Get progress
                for s in course.get('enrolled_students', []):
                    if s['user_id'] == current_user['user_id']:
                        c['progress'] = s.get('progress', 0)
                        break
                instructor = db.users.find_one({"user_id": course['instructor_id']})
                c['instructor_name'] = instructor['full_name'] if instructor else "Unknown"
                courses.append(c)
        
        return jsonify({"courses": courses}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@course_bp.route('/my/teaching', methods=['GET'])
@role_required('instructor', 'admin')
def my_teaching():
    try:
        db = get_db()
        current_user = get_current_user()
        
        courses = list(db.courses.find({"instructor_id": current_user['user_id']}).sort('created_at', -1))
        result = [serialize_course(c, include_sections=True) for c in courses]
        
        return jsonify({"courses": result}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def _update_course_stats(db, course_id):
    course = db.courses.find_one({"course_id": course_id})
    if not course:
        return
    
    total_lessons = 0
    total_duration = 0
    
    for section in course.get('sections', []):
        for lesson in section.get('lessons', []):
            total_lessons += 1
            total_duration += lesson.get('duration', 0)
    
    db.courses.update_one(
        {"course_id": course_id},
        {"$set": {"total_lessons": total_lessons, "total_duration": total_duration}}
    )
