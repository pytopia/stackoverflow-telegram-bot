import time

import emoji
from loguru import logger
from src.bot import bot
from src.constants import keyboards, states
from src.db import db
from src.run import StackBot


stackbot = StackBot(mongodb=db, telebot=bot)
DELETION_SLEEP = 10  # seconds
NUM_UNCLEANED_MESSAGES_THRESHOLD = 5

while True:
    logger.info('Start deletion process...')

    chat_ids = set()
    skip_chat_ids = set()
    for chat_id in db.auto_delete.distinct('chat_id'):
        # only users in main states
        user = db.users.find_one({'chat.id': chat_id, 'state': states.MAIN})
        if not user:
            continue

        # only users that have more than 3 uncleaned messages
        num_messages = db.auto_delete.count_documents({'chat_id': chat_id})
        if num_messages <= NUM_UNCLEANED_MESSAGES_THRESHOLD:
            continue

        # delete messages
        for doc in db.auto_delete.find({'chat_id': chat_id}):
            chat_id = doc['chat_id']
            message_id = doc['message_id']
            current_time = time.time()
            remaining_time = doc['created_at'] + doc['delete_after'] - current_time

            if remaining_time > 0:
                continue

            # delete message
            stackbot.delete_message(chat_id=chat_id, message_id=message_id)
            db.auto_delete.delete_one({'_id': doc['_id']})
            chat_ids.add(chat_id)
            logger.info(f'Deleted message {message_id} from chat {chat_id}.')

    # reset the keyboard
    for chat_id in chat_ids:
        message = stackbot.send_message(
            chat_id=chat_id,
            text=emoji.emojize(':check_mark_button: We cleaned your bot history to improve your experience.'),
            reply_markup=keyboards.main
        )

    time.sleep(DELETION_SLEEP)
