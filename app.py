from flask import Flask, jsonify
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from dotenv import load_dotenv
import os

load_dotenv()

def create_app():
    app = Flask(__name__)

    app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', 'super-secret-key-change-in-production')
    app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024

    CORS(app,
         origins="*",
         allow_headers=["Content-Type", "Authorization"],
         methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
         supports_credentials=False)

    JWTManager(app)

    from config.db import connect_db
    connect_db()

    from config.cloudinary_config import init_cloudinary
    init_cloudinary()

    _seed_admin()

    from routes.auth_routes import auth_bp
    from routes.course_routes import course_bp
    from routes.admin_routes import admin_bp

    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(course_bp, url_prefix='/api/courses')
    app.register_blueprint(admin_bp, url_prefix='/api/admin')

    @app.route('/api/health')
    def health():
        return jsonify({"status": "ok", "message": "LearnFlow API running on Vercel"}), 200

    @app.after_request
    def after_request(response):
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
        response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
        return response

    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"error": "Route not found"}), 404

    @app.errorhandler(413)
    def too_large(e):
        return jsonify({"error": "File too large. Max 500MB"}), 413

    @app.errorhandler(500)
    def server_error(e):
        return jsonify({"error": "Internal server error", "detail": str(e)}), 500

    return app


def _seed_admin():
    try:
        from config.db import get_db
        from models.user import get_user_by_email, create_user
        db = get_db()
        admin_email = os.getenv('ADMIN_EMAIL', 'admin@lms.com')
        admin_password = os.getenv('ADMIN_PASSWORD', 'Admin@123')
        if not get_user_by_email(db, admin_email):
            admin = create_user(db, admin_email, admin_password, 'Super Admin', 'admin')
            db.users.update_one({"user_id": admin['user_id']}, {"$set": {"is_approved": True}})
            print(f"✅ Admin seeded: {admin_email}")
    except Exception as e:
        print(f"⚠️  Admin seed skipped: {e}")


# Module-level instance so gunicorn can find it with `gunicorn app:app`
app = create_app()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
