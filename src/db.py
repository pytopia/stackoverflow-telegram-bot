import pymongo
from loguru import logger

def build_indexes(db):
    # users
    db.users.create_index([('chat.id', 1)], unique=True)
    db.users.create_index([('chat.id', 1), ('state', 1)])
    db.users.create_index([('attachments.file_unique_id', 1)])

    # posts
    db.post.create_index([('status', 1)])
    db.post.create_index([('type', 1)])
    db.post.create_index([('replied_to_post_id', 1)])
    db.post.create_index([('chat.id', 1)])
    db.post.create_index([('status', 1), ('type', 1), ('chat.id', 1)])
    db.post.create_index([('status', 1), ('type', 1), ('replied_to_post_id', 1)])

    # db.post.create_index([('text', 'text')])

    # callback data
    db.callback_data.create_index([('chat_id', 1)])
    db.callback_data.create_index([('message_id', 1)])
    db.callback_data.create_index([('created_at', 1)])
    db.callback_data.create_index([('chat_id', 1), ('message_id', 1)])
    db.callback_data.create_index([('chat_id', 1), ('message_id', 1), ('post_id', 1)])
    db.callback_data.create_index([('chat_id', 1), ('message_id', 1), ('created_at', 1)])

    # auto update
    db.auto_update.create_index([('chat_id', 1), ('message_id', 1)])

# MongoDB connection
client = pymongo.MongoClient("localhost", 27017)
db = client.test

# Build indexes
logger.info('Building indexes...')
build_indexes(db)
logger.info('Indexes built.')
