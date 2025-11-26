"""
Database connection utilities for MongoDB.
Provides both sync (PyMongo) and async (Motor) connections.
"""

import os
from dotenv import load_dotenv
import pymongo
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv()


def get_mongo_uri() -> str:
    """Get MongoDB connection URI from environment or use default."""
    return os.getenv("MONGO_URI", "mongodb://localhost:27017/")


# ======================
# Async MongoDB (Motor) - for FastAPI
# ======================

def get_db():
    """Get async MongoDB database connection for FastAPI.
    
    Returns:
        AsyncIOMotorDatabase: The loan_assistant_db database
    """
    mongo_uri = get_mongo_uri()
    client = AsyncIOMotorClient(mongo_uri)
    return client["loan_assistant_db"]


# ======================
# Sync MongoDB (PyMongo) - for Streamlit
# ======================

_mongo_client = None


def get_mongo_client():
    """Get sync MongoDB client for Streamlit (cached singleton).
    
    Returns:
        pymongo.MongoClient or None: MongoDB client if connection succeeds
    """
    global _mongo_client
    
    if _mongo_client is not None:
        return _mongo_client
    
    mongo_uri = get_mongo_uri()
    try:
        client = pymongo.MongoClient(mongo_uri, serverSelectionTimeoutMS=2000)
        # Check connection
        client.server_info()
        _mongo_client = client
        return client
    except Exception as e:
        print(f"MongoDB connection failed: {e}")
        return None


def get_mongo_collection(collection_name: str = "logs"):
    """Get a specific collection from the loan_assistant_db.
    
    Args:
        collection_name: Name of the collection to retrieve
        
    Returns:
        Collection or None: The requested collection if client is available
    """
    client = get_mongo_client()
    if client:
        db = client["loan_assistant_db"]
        return db[collection_name]
    return None


def get_conversations_collection():
    """Get the conversations collection for chat history."""
    return get_mongo_collection("conversations")


def get_logs_collection():
    """Get the logs collection for interaction logging."""
    return get_mongo_collection("logs")
