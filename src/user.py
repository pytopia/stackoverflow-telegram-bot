import concurrent.futures
from itertools import repeat

from loguru import logger

from src.constants import (QUESTION_PREVIEW_MESSAGE,
                           SEND_QUESTION_TO_ALL_MESSAGE,
                           SEND_TO_ALL_SUCCESS_MESSAGE, states)


class User:
    """
    Class to handle telegram bot users.
    """
    def __init__(self, chat_id, mongodb, stackbot, message):
        self.chat_id = chat_id
        self.db = mongodb
        self.stackbot = stackbot
        self.message = message
        self.first_name = self.message.chat.first_name
        self.username = self.message.chat.username

    @property
    def user(self):
        return self.db.users.find_one({'chat.id': self.chat_id})

    @property
    def state(self):
        return self.user.get('state')

    @property
    def question(self):
        """
        Get current question raw message text.
        """
        return '\n'.join(self.user.get('current_question', []))

    @property
    def current_question(self):
        """
        Get current question full message.
        """
        return QUESTION_PREVIEW_MESSAGE.format(question=self.question)

    def save_question(self):
        """
        Save question to database.
        """
        logger.info('Save question to database...')
        if not self.user.get('current_question'):
            self.send_message(text=':cross_mark: Question is empty.')
            return False

        self.db.questions.insert_one({
            'chat_id': self.chat_id,
            'question': self.user.get('current_question', []),
            'date': self.message.date,
        })
        return True

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
            {'$set': {'current_question': [], 'state': states.main}},
        )

    def send_question_to_all(self):
        """
        Send question to all users in parallel.
        """
        from_user = f'@{self.username}' if self.username else self.first_name
        msg_text = SEND_QUESTION_TO_ALL_MESSAGE.format(from_user=from_user, question=self.question)

        # Send to all users in parallel
        with concurrent.futures.ThreadPoolExecutor() as executor:
            executor.map(self.stackbot.send_message, self.db.users.distinct('chat.id'), repeat(msg_text))
        self.send_message(SEND_TO_ALL_SUCCESS_MESSAGE)


if __name__ == '__main__':
    u = User(chat_id=371998922)
    print(u.state)
