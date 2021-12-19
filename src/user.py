import concurrent.futures

import emoji
from loguru import logger

from src.constants import keys, states


class User:
    """
    Class to handle telegram bot users.
    """
    def __init__(self, chat_id, mongodb, stackbot, message):
        self.chat_id = chat_id
        self.db = mongodb
        self.stackbot = stackbot
        self.message = message

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
        question_text = ':pencil: <strong>Question Preview</strong>\n\n'
        question_text += self.question
        question_text += f'\n{"_" * 40}\nWhen done, click <strong>{keys.send_question}</strong>.'
        return question_text

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
        # TODO: Fix duplicate send_message in run.py and here
        # This is not according to DRY.
        if emojize:
            text = emoji.emojize(text)

        self.stackbot.send_message(self.chat_id, text, reply_markup=reply_markup)

    def update_state(self, state):
        """
        Update user state.
        """
        self.db.users.update_one(
            {'chat.id': self.chat_id},
            {'$set': {'state': state}},
        )

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
        user = self.user
        username = f"@{user['chat'].get('username')}"
        firstname = user['chat']['first_name']
        msg_text = f":bust_in_silhouette: From: {username or firstname}\n"
        msg_text += ':red_question_mark: <strong>New Question</strong>\n\n'
        msg_text += self.question

        # Send to all users in parallel
        with concurrent.futures.ThreadPoolExecutor() as executor:
            for chat_id in self.db.users.distinct('chat.id'):
                executor.submit(self.stackbot.send_message, chat_id, msg_text)

        self.send_message(text=':check_mark_button: Question sent successfully to all users.')


if __name__ == '__main__':
    u = User(chat_id=371998922)
    print(u.state)
