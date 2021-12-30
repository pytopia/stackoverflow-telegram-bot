import time

import emoji
from loguru import logger
from telebot import custom_filters

from handlers.command_handlers import register_command_handlers
from handlers.message_handlers import register_message_handlers
from handlers.callback_handlers import register_callback_handlers
from src import constants
from src.bot import bot
from src.constants import (DELETE_BOT_MESSAGES_AFTER_TIME, inline_keys,
                           keyboards)
from src.data_models.post import Post
from src.db import db
from src.filters import IsAdmin
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
        register_command_handlers(self)
        register_message_handlers(self)
        register_callback_handlers(self)

    def send_gallery(self, chat_id, post_id, is_gallery=False, gallery_filters=None):
        """
        Send gallery of posts starting with the post with post_id.

        :param chat_id: Chat id to send gallery to.
        :param post_id: Post id to start gallery from.
        :param is_gallery: If True, send gallery of posts. If False, send single post.
            Next and previous buttions will be added to the message if is_gallery is True.
        """
        post_handler = Post(
            mongodb=self.user.db, stackbot=self.user.stackbot,
            post_id=post_id, chat_id=self.user.chat_id,
            is_gallery=is_gallery, gallery_filters=gallery_filters
        )
        message = self.user.send_message(
            text=post_handler.get_text(),
            reply_markup=post_handler.get_keyboard(),
            delete_after=False,
        )

        # if user asks for this gallery again, we delete the old one to keep the history clean.
        self.user.clean_preview(message.message_id)

        # we should store the callback data for the new message
        self.db.callback_data.update_one(
            {'chat_id': chat_id, 'message_id': message.message_id},
            {'$set': {'post_id': post_id, 'preview': False, 'is_gallery': is_gallery}},
            upsert=True
        )

        return message

    def edit_gallery(self, call, next_post_id, is_gallery=False, gallery_fiters=None):
        """
        Edit gallery of posts to show next or previous post. Next post to show is the one
        with post_id=next_post_id.

        :param chat_id: Chat id to send gallery to.
        :param next_post_id: post_id of the next post to show.
        :param is_gallery: If True, send gallery of posts. If False, send single post.
            Next and previous buttions will be added to the message if is_gallery is True.
        """
        post_handler = Post(
            mongodb=self.user.db, stackbot=self.user.stackbot,
            post_id=next_post_id, chat_id=self.user.chat_id,
            is_gallery=is_gallery, gallery_filters=gallery_fiters
        )

        self.edit_message(
            call.message.chat.id, call.message.message_id,
            text=post_handler.get_text(),
            reply_markup=post_handler.get_keyboard()
        )

        # we should update the post_id for the buttons cause it is a new post
        self.db.callback_data.update_one(
            {'chat_id': call.message.chat.id, 'message_id': call.message.message_id},
            {'$set': {'post_id': next_post_id, 'preview': False, 'is_gallery': is_gallery}},
        )

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

        self.queue_delete_message(chat_id, message.message_id, delete_after)
        return message

    def queue_delete_message(self, chat_id, message_id, delete_after):
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

    def send_file(self, chat_id, file_unique_id, message_id=None):
        """
        Send file to telegram bot having a chat_id and file_id.
        """
        file_id, content_type, mime_type = self.file_unique_id_to_content(file_unique_id)

        # Send file to user with the appropriate send_file method according to the content_type
        send_method = getattr(self.bot, f'send_{content_type}')
        message = send_method(
            chat_id, file_id,
            reply_to_message_id=message_id,
            caption=f"<code>{mime_type or ''}</code>",
        )

        # Delete message after a while
        self.queue_delete_message(chat_id, message.message_id, DELETE_BOT_MESSAGES_AFTER_TIME)

    def file_unique_id_to_content(self, file_unique_id):
        """
        Get file content having a file_id.
        """
        query_result = self.db.post.find_one({'content.file_unique_id': file_unique_id}, {'content.$': 1})
        if not query_result:
            return

        content = query_result['content'][0]
        return content['file_id'], content['content_type'], content.get('mime_type')

    def delete_message(self, chat_id, message_id):
        """
        Delete bot message.
        """
        try:
            self.bot.delete_message(chat_id, message_id)
        except Exception as e:
            logger.debug('Error deleting message: Message not found.')

    def get_call_info(self, call):
        """
        Get call info from call data.

        Every message with inline keyboard has information stored in database, particularly the post_id.

        We store the post_id in the database to use it later when user click on any inline button.
        For example, if user click on 'answer' button, we know which post_id to store answer for.
        This post_id is stored in the database as 'replied_to_post_id' field.

        We also store post_type in the database to use the right handler in user object (Question, Answer, Comment).
        """
        callback_data = self.db.callback_data.find_one({'chat_id': call.message.chat.id, 'message_id': call.message.message_id})
        return callback_data or {}

    def get_gallery_filters(self, chat_id, message_id):
        result = self.db.callback_data.find_one({'chat_id': chat_id, 'message_id': message_id})
        if not result:
            return {}
        return result.get('gallery_filters', {})

    def answer_callback_query(self, call_id, text, emojize=True):
        """
        Answer to a callback query.
        """
        if emojize:
            text = emoji.emojize(text)
        self.bot.answer_callback_query(call_id, text=text)

    def get_settings_keyboard(self):
        """
        Returns settings main menu keyboard.
        """
        muted_bot = self.user.settings.get('muted_bot')
        if muted_bot:
            keys = [inline_keys.change_identity, inline_keys.unmute]
        else:
            keys = [inline_keys.change_identity, inline_keys.mute]

        return create_keyboard(*keys, is_inline=True)

    def get_settings_text(self):
        """
        Returns settings text message.
        """
        text = constants.SETTINGS_START_MESSAGE.format(
            first_name=self.user.first_name,
            username=self.user.username,
            identity=self.user.identity,
        )
        return text

if __name__ == '__main__':
    logger.info('Bot started...')
    stackbot = StackBot(telebot=bot, mongodb=db)
    stackbot.run()
