from loguru import logger

from src import constants
from src.constants import states
from src.data_models.answer import Answer
from src.data_models.post import Post
from src.data_models.question import Question


class User:
    """
    Class to handle telegram bot users.
    """
    def __init__(self, chat_id, mongodb, stackbot, first_name=None, post_type=None):
        self.chat_id = chat_id
        self.db = mongodb
        self.stackbot = stackbot
        self.first_name = first_name
        self.post_type = post_type

    @property
    def user(self):
        return self.db.users.find_one({'chat.id': self.chat_id})

    @property
    def state(self):
        return self.user.get('state')

    @property
    def tracker(self):
        return self.user.get('tracker')

    @property
    def post(self):
        """
        Return the right post handler based on user state or post type.
        """
        if self.post_type == 'question':
            post_handler = Question(mongodb=self.db, stackbot=self.stackbot)
        elif self.post_type == 'answer':
            post_handler = Answer(mongodb=self.db, stackbot=self.stackbot)
        elif self.state == states.ASK_QUESTION:
            post_handler = Question(mongodb=self.db, stackbot=self.stackbot)
        elif self.state == states.ANSWER_QUESTION:
            post_handler = Answer(mongodb=self.db, stackbot=self.stackbot)
        else:
            post_handler = Post(mongodb=self.db, stackbot=self)

        post_handler.chat_id = self.chat_id
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
            {'$set': {'state': states.MAIN}}
        )

        for collection in [self.db.question, self.db.answer]:
            collection.delete_one({'chat.id': self.chat_id, 'status': constants.post_status.PREP})

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

        if new_preview_message:
            self.track(preview_message_id=new_preview_message.message_id)
