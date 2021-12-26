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

        # Post handlers
        self.post_handler = Post(mongodb=self.db, stackbot=self.stackbot)
        self.question = Question(mongodb=self.db, stackbot=self.stackbot)
        self.answer = Answer(mongodb=self.db, stackbot=self.stackbot)

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
            post_handler = self.question
        elif self.post_type == 'answer':
            post_handler = self.answer
        elif self.state == states.ASK_QUESTION:
            post_handler = self.question
        elif self.state == states.ANSWER_QUESTION:
            post_handler = self.answer
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
        self.db.users.update_one(
            {'chat.id': self.chat_id},
            {'$set': {'tracker': kwargs}}
        )
