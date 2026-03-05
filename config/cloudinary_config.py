import cloudinary
import cloudinary.uploader
import cloudinary.api
import os
from dotenv import load_dotenv

load_dotenv()

def init_cloudinary():
    cloudinary.config(
        cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
        api_key=os.getenv("CLOUDINARY_API_KEY"),
        api_secret=os.getenv("CLOUDINARY_API_SECRET"),
        secure=True
    )
    print("✅ Cloudinary configured")

def upload_video(file, folder="lms/videos"):
    try:
        result = cloudinary.uploader.upload_large(
            file,
            resource_type="video",
            folder=folder,
            eager=[{"streaming_profile": "full_hd", "format": "m3u8"}],
            eager_async=True
        )
        return {
            "public_id": result.get("public_id"),
            "url": result.get("secure_url"),
            "duration": result.get("duration", 0),
            "format": result.get("format"),
            "bytes": result.get("bytes", 0)
        }
    except Exception as e:
        raise Exception(f"Video upload failed: {str(e)}")

def upload_file(file, folder="lms/notes"):
    try:
        result = cloudinary.uploader.upload(
            file,
            resource_type="raw",
            folder=folder
        )
        return {
            "public_id": result.get("public_id"),
            "url": result.get("secure_url"),
            "format": result.get("format"),
            "bytes": result.get("bytes", 0)
        }
    except Exception as e:
        raise Exception(f"File upload failed: {str(e)}")

def upload_image(file, folder="lms/thumbnails"):
    try:
        result = cloudinary.uploader.upload(
            file,
            resource_type="image",
            folder=folder,
            transformation=[{"width": 800, "height": 450, "crop": "fill"}]
        )
        return {
            "public_id": result.get("public_id"),
            "url": result.get("secure_url")
        }
    except Exception as e:
        raise Exception(f"Image upload failed: {str(e)}")

def delete_resource(public_id, resource_type="video"):
    try:
        cloudinary.uploader.destroy(public_id, resource_type=resource_type)
    except Exception as e:
        print(f"Delete failed: {e}")
