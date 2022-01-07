import time

from loguru import logger
from src.bot import bot
from src.constants import states
from src.db import db
from src.run import StackBot


stackbot = StackBot(db=db, telebot=bot)
DELETION_SLEEP = 10  # seconds
KEEP_LAST_MESSAGES_NUMBER = 3

while True:
    print('Start deletion process...')
    chat_ids = set()
    skip_chat_ids = set()
    for chat_id in db.auto_delete.distinct('chat_id'):
        # Only users in main states
        user = db.users.find_one({'chat.id': chat_id, 'state': states.MAIN})
        if not user:
            continue

        # Only users that have more than 3 uncleaned messages
        num_messages = db.auto_delete.count_documents({'chat_id': chat_id})

        # Delete messages
        for ind, doc in enumerate(db.auto_delete.find({'chat_id': chat_id})):
            chat_id = doc['chat_id']
            message_id = doc['message_id']
            current_time = time.time()

            # Don't delete the last message
            if ind >= (num_messages - KEEP_LAST_MESSAGES_NUMBER):
                continue

            # -1 flag shows the message should not be deleted
            if doc['delete_after'] == -1:
                continue

            remaining_time = doc['created_at'] + doc['delete_after'] - current_time
            if remaining_time > 0:
                continue

            # Delete message
            stackbot.delete_message(chat_id=chat_id, message_id=message_id)
            db.auto_delete.delete_one({'_id': doc['_id']})

            # Delete message in callback data and auto_update data
            db.callback_data.delete_many({'chat_id': chat_id, 'message_id': message_id})
            db.auto_update.delete_many({'chat_id': chat_id, 'message_id': message_id})

            chat_ids.add(chat_id)

    time.sleep(DELETION_SLEEP)
