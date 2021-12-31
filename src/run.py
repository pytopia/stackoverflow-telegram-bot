import time

import emoji
from loguru import logger
from telebot import custom_filters

from src.bot import bot
from src.constants import (DELETE_BOT_MESSAGES_AFTER_TIME,
                           SETTINGS_START_MESSAGE, inline_keys, keyboards)
from src.db import db
from src.filters import IsAdmin
from src.handlers import CallbackHandler, CommandHandler, MessageHandler
from src.utils.keyboard import create_keyboard


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
        self.register_handlers()

    def run(self):
        # run bot with polling
        logger.info('Bot is running...')
        self.bot.infinity_polling()

    def register_handlers(self):
        """
        Register all handlers.
        """
        # Command handlers for commands such as /start /help /settings etc.
        command_handlers = CommandHandler(stack=self, db=self.db)
        command_handlers.register()

        # Message handlers for text messages
        message_handlers = MessageHandler(stack=self, db=self.db)
        message_handlers.register()

        # Callback handlers for inline buttons
        callback_handlers = CallbackHandler(stack=self, db=self.db)
        callback_handlers.register()

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
            delete_after = -1
            prev_doc = self.db.auto_delete.find_one({
                'chat_id': chat_id, 'delete_after': -1
            })
            if prev_doc:
                self.delete_message(chat_id, prev_doc['message_id'])
                db.auto_delete.delete_one({'_id': prev_doc['_id']})

        self.queue_message_deletion(chat_id, message.message_id, delete_after)
        return message

    def queue_message_deletion(self, chat_id, message_id, delete_after):
        if not delete_after:
            return

        self.db.auto_delete.insert_one({
            'chat_id': chat_id, 'message_id': message_id,
            'delete_after': delete_after, 'created_at': time.time(),
        })

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
        except Exception as e:
            logger.debug(e)

    def delete_message(self, chat_id, message_id):
        """
        Delete bot message.
        """
        try:
            self.bot.delete_message(chat_id, message_id)
        except Exception as e:
            logger.debug('Error deleting message: Message not found.')

if __name__ == '__main__':
    logger.info('Bot started...')
    stackbot = StackBot(telebot=bot, mongodb=db)
    stackbot.run()
