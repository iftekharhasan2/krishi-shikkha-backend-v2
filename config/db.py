from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
import os
from dotenv import load_dotenv

load_dotenv()

client = None
db = None

def connect_db():
    global client, db
    try:
        mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017/lms_db")
        client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
        client.admin.command('ping')
        db = client.get_database("lms_db")
        print("✅ MongoDB connected successfully")
        return db
    except ConnectionFailure as e:
        print(f"❌ MongoDB connection failed: {e}")
        raise

def get_db():
    global db
    if db is None:
        connect_db()
    return db
