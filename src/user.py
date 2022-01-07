from typing import Union

from loguru import logger
from telebot import types

from src import constants
from src.constants import (DELETE_BOT_MESSAGES_AFTER_TIME, inline_keys,
                           keyboards, post_types, states)
from src.data_models import Answer, Comment, Question
from src.data_models.base import BasePost


class User:
    """
    Class to handle telegram bot users.
    """
    def __init__(self, chat_id: str, first_name: str, db, stackbot, post_id: str = None):
        """
        Initialize user.

        :param chat_id: Telegram chat id.
        :param db: MongoDB connection.
        :param stackbot: StackBot class object.
        :param first_name: User first name.
        :param post_id: ObjectId of the post, defaults to None.
        """
        self.chat_id = chat_id
        self.db = db
        self.stackbot = stackbot
        self.first_name = first_name

        # post handlers
        self.post_id = post_id
        self._post = None

    @staticmethod
    def get_post_handler(state, post_type):
        if (post_type == post_types.QUESTION) or (state == states.ASK_QUESTION):
            return Question
        elif (post_type == post_types.ANSWER) or (state == states.ANSWER_QUESTION):
            return Answer
        elif (post_type == post_types.COMMENT) or (state == states.COMMENT_POST):
            return Comment

        return BasePost

    @property
    def post(self):
        """
        Return the right post handler based on user state or post type.
        """
        if self._post is not None:
            return self._post

        post = self.db.post.find_one({'_id': self.post_id}) or {}
        args = dict(db=self.db, stackbot=self.stackbot, chat_id=self.chat_id, post_id=self.post_id)
        self._post = self.get_post_handler(self.state, post['type'])(**args)

        return self._post

    @post.setter
    def post(self, post_handler):
        if not isinstance(post_handler, BasePost):
            raise TypeError('Post must be an instance of BasePost (Question, Answer, Comment).')

        args = dict(
            db=post_handler.db, stackbot=post_handler.stackbot, chat_id=post_handler.chat_id,
            is_gallery=post_handler.is_gallery, gallery_filters=post_handler.gallery_filters,
            post_id=post_handler.post_id,
        )

        post_type = self.db.post.find_one({'_id': post_handler.post_id})['type']
        self._post = self.get_post_handler(self.state, post_type)(**args)

    @property
    def user(self):
        return self.db.users.find_one({'chat.id': self.chat_id}) or {}

    @property
    def state(self):
        return self.user.get('state')

    @property
    def tracker(self):
        return self.user.get('tracker', {})

    @property
    def settings(self):
        return self.user.get('settings')

    @property
    def username(self):
        username = self.user['chat'].get('username')
        return f'@{username}' if username else None

    @property
    def identity(self):
        """
        User can have a custom identity:
            - ananymous
            - username
            - first name

        User identity is set from settings menu.
        """
        user = self.user
        username = self.username

        identity_type = user['settings']['identity_type']
        if identity_type == inline_keys.ananymous:
            return self.chat_id
        elif (identity_type == inline_keys.username) and (username is not None):
            return username
        elif identity_type == inline_keys.first_name:
            return f"{user['chat']['first_name']} ({self.chat_id})"

        return user['chat'].get(identity_type) or self.chat_id

    def send_message(
        self, text: str, reply_markup: Union[types.InlineKeyboardMarkup, types.ReplyKeyboardMarkup] = None,
        emojize: bool = True, delete_after: Union[bool, int] = DELETE_BOT_MESSAGES_AFTER_TIME
    ):
        """
        Send message to user.

        :param text: Message text.
        :param reply_markup: Message reply markup.
        :param emojize: Emojize text, defaults to True.
        """
        message = self.stackbot.send_message(
            chat_id=self.chat_id, text=text, reply_markup=reply_markup,
            emojize=emojize, delete_after=delete_after
        )

        return message

    def edit_message(self, message_id, text=None, reply_markup=None, emojize: bool = True):
        self.stackbot.edit_message(
            chat_id=self.chat_id, message_id=message_id, text=text,
            reply_markup=reply_markup, emojize=emojize
        )

    def delete_message(self, message_id: str):
        """
        Delete user message.

        :param message_id: Message id to delete.
        """
        self.stackbot.delete_message(chat_id=self.chat_id, message_id=message_id)

    def clean_preview(self, new_preview_message_id=None):
        """
        Preview message is used to show the user the post that is going to be created.
        This method deletes the previous preview message and keeps track of the new one.

        :param new_preview_message: New preview message to track after deleting the old one, defaults to None.
        """
        old_preview_message_id = self.tracker.get('preview_message_id')
        if old_preview_message_id:
            self.delete_message(old_preview_message_id)
            self.untrack('preview_message_id')

        if new_preview_message_id:
            self.track(preview_message_id=new_preview_message_id)

    def update_state(self, state: str):
        """
        Update user state.

        :param state: New state.
        """
        self.db.users.update_one({'chat.id': self.chat_id}, {'$set': {'state': state}})

    def reset(self):
        """
        Reset user state and data.
        """
        logger.info('Reset user data.')
        self.db.users.update_one(
            {'chat.id': self.chat_id},
            {'$set': {'state': states.MAIN}, '$unset': {'tracker': 1}}
        )

        self.db.post.delete_one({'chat.id': self.chat_id, 'status': constants.post_status.PREP})

    def register(self, message):
        logger.info('Registering user...')
        self.send_message(
            constants.WELCOME_MESSAGE.format(first_name=self.first_name),
            reply_markup=keyboards.main,
            delete_after=False
        )
        self.db.users.update_one({'chat.id': message.chat.id}, {'$set': message.json}, upsert=True)
        self.update_settings(identity_type=inline_keys.ananymous, muted_bot=False)
        self.reset()

    @property
    def is_registered(self):
        """
        Check if user exists in database.
        """
        if self.db.users.find_one({'chat.id': self.chat_id}) is None:
            return False

        return True

    def track(self, **kwargs):
        """
        Track user actions and any other data.
        """
        track_data = self.tracker
        track_data.update(kwargs)
        self.db.users.update_one(
            {'chat.id': self.chat_id},
            {'$set': {'tracker': track_data}}
        )

    def untrack(self, *args):
        self.db.users.update_one(
            {'chat.id': self.chat_id},
            {'$unset': {f'tracker.{arg}': 1 for arg in args}}
        )

    def update_settings(self, **kwargs):
        """
        Update user settings.
        """
        settings = {f'settings.{key}': value for key, value in kwargs.items()}
        self.db.users.update_one(
            {'chat.id': self.chat_id},
            {'$set': settings}
        )
