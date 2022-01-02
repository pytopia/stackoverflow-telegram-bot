import pymongo
from loguru import logger

client = pymongo.MongoClient("localhost", 27017)
db = client.test
# db.drop_collection('users')

logger.info('Building indexes...')
db.users.create_index([('chat.id', 1)], unique=True)
db.users.create_index([('chat.id', 1), ('state', 1)])
db.users.create_index([('content.file_unique_id', 1)])

db.callback_data.create_index([('chat_id', 1)])
db.callback_data.create_index([('message_id', 1)])
db.callback_data.create_index([('created_at', 1)])
db.callback_data.create_index([('chat_id', 1), ('message_id', 1)])
db.callback_data.create_index([('chat_id', 1), ('message_id', 1), ('post_id', 1)])
db.callback_data.create_index([('chat_id', 1), ('message_id', 1), ('created_at', 1)])

db.post.create_index([('status', 1), ('type', 1)])
db.post.create_index([('status', 1), ('type', 1), ('chat.id', 1)])
db.post.create_index([('status', 1), ('type', 1), ('replied_to_post_id', 1)])

db.auto_update.create_index([('chat_id', 1), ('message_id', 1)])

logger.info('Indexes built.')
