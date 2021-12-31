import re
import time

import emoji
from loguru import logger
from telebot import custom_filters, types

from src.bot import bot
from src.constants import (DELETE_BOT_MESSAGES_AFTER_TIME,
                           DELETE_FILE_MESSAGES_AFTER_TIME, keyboards)
from src.db import db
from src.filters import IsAdmin
from src.handlers import CallbackHandler, CommandHandler, MessageHandler


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
            MessageHandler(stack=self, db=self.db),
            CallbackHandler(stack=self, db=self.db),
            CommandHandler(stack=self, db=self.db),
        ]
        self.register()

    def run(self):
        # run bot with polling
        logger.info('Bot is running...')
        self.bot.infinity_polling()

    def register(self):
        for handler in self.handlers:
            handler.register()

    def send_message(self, chat_id, text, reply_markup=None, emojize=True, delete_after=DELETE_BOT_MESSAGES_AFTER_TIME):
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

        if reply_markup == keyboards.main and delete_after is not False:
            # We need to keep the message which generated main keyboard so that
            # it does not go away. Otherwise, the user will be confused and won't have
            # any keyboaard to interact with.
            # To indicate this message, we set its delete_after to -1.
            delete_after = -1
            prev_doc = self.db.auto_delete.find_one({'chat_id': chat_id, 'delete_after': -1})
            if prev_doc:
                # remove the previous message with such a keyboard
                self.delete_message(chat_id, prev_doc['message_id'])
                db.auto_delete.delete_one({'_id': prev_doc['_id']})

        self.queue_message_deletion(chat_id, message.message_id, delete_after)
        self.update_callback_data(message.message_id, reply_markup)

        return message

    def edit_message(self, chat_id, message_id, text=None, reply_markup=None, emojize: bool = True):
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

            self.update_callback_data(message_id, reply_markup)
        except Exception as e:
            logger.debug(f'Error editing message: {e}')

    def delete_message(self, chat_id, message_id):
        """
        Delete bot message.
        """
        try:
            self.bot.delete_message(chat_id, message_id)
            self.db.callback_data.delete_many({'chat_id': chat_id, 'message_id': message_id})
        except Exception as e:
            logger.debug(f'Error deleting message: {e}')

    def send_file(self, chat_id, file_unique_id, message_id=None, delete_after=DELETE_FILE_MESSAGES_AFTER_TIME):
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

    def file_unique_id_to_content(self, file_unique_id):
        """
        Get file content having a file_id.
        """
        query_result = self.db.post.find_one({'content.file_unique_id': file_unique_id}, {'content.$': 1})
        if not query_result:
            return

        return query_result['content'][0]

    def retrive_post_id_from_message_text(self, text):
        """
        Get post_id from message text.
        """
        text = emoji.demojize(text)
        last_line = text.split('\n')[-1]
        pattern = '^:ID_button: (?P<id>[A-Za-z0-9]+)$'
        match = re.match(pattern, last_line)
        post_id = match.group('id') if match else None
        return post_id

    def queue_message_deletion(self, chat_id, message_id, delete_after):
        if not delete_after:
            return

        self.db.auto_delete.insert_one({
            'chat_id': chat_id, 'message_id': message_id,
            'delete_after': delete_after, 'created_at': time.time(),
        })

    def update_callback_data(self, message_id, reply_markup):
        if reply_markup and isinstance(reply_markup, types.InlineKeyboardMarkup):
            logger.info(f'Updating callback data for message {message_id}')

            self.db.callback_data.update_one(
                {
                    'chat_id': self.user.chat_id,
                    'message_id': message_id,
                    'post_id': self.user.post.post_id,
                },
                {
                    '$set': {
                        'is_gallery': self.user.post.is_gallery,
                        'gallery_filters': self.user.post.gallery_filters,
                    }
                },
                upsert=True
            )



if __name__ == '__main__':
    logger.info('Bot started...')
    stackbot = StackBot(telebot=bot, mongodb=db)
    stackbot.run()
