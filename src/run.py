import re
import sys
import time
from typing import Union

import emoji
from bson.objectid import ObjectId
from loguru import logger
from telebot import custom_filters, types

from src.bot import bot
from src.constants import (DELETE_BOT_MESSAGES_AFTER_TIME,
                           DELETE_FILE_MESSAGES_AFTER_TIME)
from src.db import db
from src.filters import IsAdmin
from src.handlers import CallbackHandler, CommandHandler, MessageHandler

logger.remove()
logger.add(sys.stderr, format="{time} {level} {message}", level="ERROR")

class StackBot:
    """
    Stackoverflow Telegram Bot.

    Using the Telegram Bot API, users can interact with each other to ask questions,
    comment, and answer.
    """
    def __init__(self, telebot, mongodb):
        self.bot = telebot
        self.db = mongodb

        # add custom filters
        self.bot.add_custom_filter(IsAdmin())
        self.bot.add_custom_filter(custom_filters.TextMatchFilter())
        self.bot.add_custom_filter(custom_filters.TextStartsFilter())

        # register handlers
        self.user = None

        # Note: The order of handlers matters as the first
        # handler that matches a message will be executed.
        self.handlers = [
            CommandHandler(stack=self, db=self.db),
            MessageHandler(stack=self, db=self.db),
            CallbackHandler(stack=self, db=self.db),
        ]
        self.register()

    def run(self):
        # run bot with polling
        logger.info('Bot is running...')
        self.bot.infinity_polling()

    def register(self):
        for handler in self.handlers:
            handler.register()

    def send_message(
        self, chat_id: int, text: str,
        reply_markup: Union[types.ReplyKeyboardMarkup, types.InlineKeyboardMarkup] = None,
        emojize: bool = True,
        delete_after: Union[int, bool] = DELETE_BOT_MESSAGES_AFTER_TIME,
        auto_update: bool = False,
    ):
        """
        Send message to telegram bot having a chat_id and text_content.

        :param chat_id: Chat id of the user.
        :param text: Text content of the message.
        :param reply_markup: Reply markup of the message.
        :param emojize: Emojize the text.
        :param delete_after: Auto delete message in seconds.
        """
        text = emoji.emojize(text) if emojize else text
        message = self.bot.send_message(chat_id, text, reply_markup=reply_markup)

        if auto_update:
            self.queue_message_update(chat_id, message.message_id)

        if (type(delete_after) == int) and isinstance(reply_markup, types.ReplyKeyboardMarkup):
            # We need to keep the message which generated main keyboard so that
            # it does not go away. Otherwise, the user will be confused and won't have
            # any keyboaard to interact with.
            # To indicate this message, we set its delete_after to -1.
            logger.warning(f'Setting delete_after to -1 for message with message_id: {message.message_id}')
            delete_after = -1
            self.db.auto_delete.update_many(
                {'chat_id': chat_id, 'delete_after': -1},
                {'$set': {'delete_after': 1}}
            )
            self.queue_message_deletion(chat_id, message.message_id, delete_after)
        elif delete_after:
            self.queue_message_deletion(chat_id, message.message_id, delete_after)

        # If user is None, we don't have to update any callback data.
        # The message is sent by the bot and not by the user.
        if self.user is not None:
            self.update_callback_data(chat_id, message.message_id, reply_markup)
        else:
            logger.warning("User is None, callback data won't be updated.")

        return message

    def edit_message(
        self, chat_id: int, message_id: int, text: str = None,
        reply_markup: Union[types.ReplyKeyboardMarkup, types.InlineKeyboardMarkup] = None,
        emojize: bool = True,
    ):
        """
        Edit telegram message text and/or reply_markup.
        """
        if emojize and text:
            text = emoji.emojize(text)

        # if message text or reply_markup is the same as before, telegram raises an invalid request error
        # so we are doing try/catch to avoid this.
        try:
            if text and reply_markup:
                self.bot.edit_message_text(text=text, reply_markup=reply_markup, chat_id=chat_id, message_id=message_id)
            elif reply_markup:
                self.bot.edit_message_reply_markup(chat_id=chat_id, message_id=message_id, reply_markup=reply_markup)
            elif text:
                self.bot.edit_message_text(text=text, chat_id=chat_id, message_id=message_id)

            self.update_callback_data(chat_id, message_id, reply_markup)
        except Exception as e:
            logger.debug(f'Error editing message: {e}')

    def delete_message(self, chat_id: int, message_id: int):
        """
        Delete bot message.
        """
        try:
            self.bot.delete_message(chat_id, message_id)
            self.db.callback_data.delete_many({'chat_id': chat_id, 'message_id': message_id})
        except Exception as e:
            logger.debug(f'Error deleting message: {e}')

    def send_file(
        self, chat_id: int, file_unique_id: str, message_id: int = None,
        delete_after=DELETE_FILE_MESSAGES_AFTER_TIME
    ):
        """
        Send file to telegram bot having a chat_id and file_id.
        """
        content = self.file_unique_id_to_content(file_unique_id)
        if not content:
            return

        file_id, content_type, mime_type = content['file_id'], content['content_type'], content.get('mime_type')

        # Send file to user with the appropriate send_file method according to the content_type
        send_method = getattr(self.bot, f'send_{content_type}')
        message = send_method(
            chat_id, file_id,
            reply_to_message_id=message_id,
            caption=f"<code>{mime_type or ''}</code>",
        )

        self.queue_message_deletion(chat_id, message.message_id, delete_after)

    def file_unique_id_to_content(self, file_unique_id: str):
        """
        Get file content having a file_id.
        """
        query_result = self.db.post.find_one({'content.file_unique_id': file_unique_id}, {'content.$': 1})
        if not query_result:
            return

        return query_result['content'][0]

    def retrive_post_id_from_message_text(self, text: str):
        """
        Get post_id from message text.
        """
        text = emoji.demojize(text)
        last_line = text.split('\n')[-1]
        pattern = '^:ID_button: (?P<id>[A-Za-z0-9]+)$'
        match = re.match(pattern, last_line)
        post_id = match.group('id') if match else None
        return ObjectId(post_id)

    def queue_message_deletion(self, chat_id: int, message_id: int, delete_after: Union[int, bool]):
        self.db.auto_delete.insert_one({
            'chat_id': chat_id, 'message_id': message_id,
            'delete_after': delete_after, 'created_at': time.time(),
        })

    def queue_message_update(self, chat_id: int, message_id: int):
        self.db.auto_update.insert_one({
            'chat_id': chat_id, 'message_id': message_id, 'created_at': time.time(),
        })

    def update_callback_data(
        self, chat_id: int, message_id: int,
        reply_markup: Union[types.ReplyKeyboardMarkup, types.InlineKeyboardMarkup]
    ):
        if reply_markup and isinstance(reply_markup, types.InlineKeyboardMarkup):

            # If the reply_markup is an inline keyboard with actions button, it is the main keyboard and
            # we update its data once in a while to keep it fresh with number of likes, etc.
            buttons = []
            for sublist in reply_markup.keyboard:
                sub_buttons = map(lambda button: emoji.demojize(button.text), sublist)
                buttons.extend(list(sub_buttons))

            self.db.callback_data.update_one(
                {
                    'chat_id': chat_id,
                    'message_id': message_id,
                    'post_id': self.user.post.post_id,
                },
                {
                    '$set': {
                        'is_gallery': self.user.post.is_gallery,
                        'gallery_filters': self.user.post.gallery_filters,

                        # We need the buttons to check to not update it asynchroneously
                        # with the wrong keys.
                        'buttons': buttons,

                        # We need the date of the callback data update to get the current active post on
                        # the gallery for refreshing post info such as likes, answers, etc.
                        'created_at': time.time()
                    }
                },
                upsert=True
            )

if __name__ == '__main__':
    logger.info('Bot started...')
    stackbot = StackBot(telebot=bot, mongodb=db)
    stackbot.run()
