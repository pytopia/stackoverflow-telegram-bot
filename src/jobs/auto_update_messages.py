import concurrent.futures
import time

from loguru import logger
from src.bot import bot
from src.constants import inline_keys
from src.data_models.base import BasePost
from src.db import db
from src.run import StackBot


stackbot = StackBot(mongodb=db, telebot=bot)
UPDATE_SLEEP = 1 * 60  # seconds
UPDATE_DELAY = 30


def update_message(update_doc):
    chat_id = update_doc['chat_id']
    message_id = update_doc['message_id']

    callback_data = db.callback_data.find(
        {'chat_id': chat_id, 'message_id': message_id}
    ).sort('created_at', -1)

    try:
        callback_data = next(callback_data)
    except StopIteration:
        db.auto_update.delete_one({'_id': update_doc['_id']})
        return

    current_time = time.time()
    if (current_time - callback_data['created_at']) < UPDATE_DELAY:
        return

    post_handler = BasePost(
        mongodb=db, stackbot=stackbot, post_id=callback_data['post_id'], chat_id=chat_id,
        is_gallery=callback_data['is_gallery'], gallery_filters=callback_data['gallery_filters']
    )

    text, keyboard = post_handler.get_text_and_keyboard()
    if (inline_keys.show_less not in callback_data['buttons']) and (inline_keys.actions in callback_data['buttons']):
        stackbot.edit_message(chat_id, message_id, text=text, reply_markup=keyboard)

while True:
    print('Start update process...')
    # with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
    #     for update_doc in db.auto_update.find():
    #         executor.submit(update_message, update_doc)

    for update_doc in db.auto_update.find():
        try:
            update_message(update_doc)
        except Exception as e:
            logger.exception(e)

    time.sleep(UPDATE_SLEEP)
