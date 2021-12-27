from loguru import logger

from src import constants
from src.constants import states
from src.data_models.answer import Answer
from src.data_models.comment import Comment
from src.data_models.post import Post
from src.data_models.question import Question


class User:
    """
    Class to handle telegram bot users.
    """
    def __init__(self, chat_id, mongodb, stackbot, first_name=None, post_id=None):
        self.chat_id = chat_id
        self.db = mongodb
        self.stackbot = stackbot
        self.first_name = first_name

        # Get the post user is working on
        # When user clicks on inline buttons, we have the post_id in our database.
        self.post_id = post_id
        self.post_type = None
        if post_id is not None:
            self.post_type = self.db.post.find_one({'_id': self.post_id})['post_type']

        # post handlers
        self.question = Question(mongodb, stackbot, chat_id=chat_id)
        self.answer = Answer(mongodb, stackbot, chat_id=chat_id)
        self.comment = Comment(mongodb, stackbot, chat_id=chat_id)

    @property
    def user(self):
        return self.db.users.find_one({'chat.id': self.chat_id})

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
        user = self.user
        username = self.username

        identity_type = user['settings']['identity_type']

        if identity_type == 'ananymous':
            return self.chat_id

        if (identity_type == 'username') and (username is not None):
            return username

        if not user['chat'].get(identity_type):
            self.send_message(constants.IDENTITY_TYPE_NOT_SET_WARNING.format(identity_type=identity_type))
            return self.chat_id

        return user['chat'][identity_type]

    @property
    def post(self):
        """
        Return the right post handler based on user state or post type.
        """
        if (self.post_type == 'question') or (self.state == states.ASK_QUESTION):
            post_handler = self.question
        elif (self.post_type == 'answer') or (self.state == states.ANSWER_QUESTION):
            post_handler = self.answer
        elif (self.post_type == 'comment') or (self.state == states.COMMENT_POST):
            post_handler = self.comment
        else:
            post_handler = Post(self.mongodb, self.stackbot, chat_id=self.chat_id)

        return post_handler

    def send_message(self, text, reply_markup=None, emojize=True):
        """
        Send message to user.
        """
        self.stackbot.send_message(chat_id=self.chat_id, text=text, reply_markup=reply_markup, emojize=emojize)

    def update_state(self, state):
        """
        Update user state.
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

    def exists(self):
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

    def delete_message(self, message_id):
        """
        Delete user message.
        """
        self.stackbot.delete_message(chat_id=self.chat_id, message_id=message_id)

    def clean_preview(self, new_preview_message=None):
        """
        Preview message is used to show the user the post that is going to be created.
        This method deletes the previous preview message and keeps track of the new one.
        """
        old_preview_message_id = self.tracker.get('preview_message_id')
        if old_preview_message_id:
            self.delete_message(old_preview_message_id)
            self.untrack('preview_message_id')

        if new_preview_message:
            self.track(preview_message_id=new_preview_message.message_id)

    def update_settings(self, **kwargs):
        """
        Update user settings.
        """
        settings = {f'settings.{key}': value for key, value in kwargs.items()}
        self.db.users.update_one(
            {'chat.id': self.chat_id},
            {'$set': settings}
        )
