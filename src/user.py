import concurrent.futures
from itertools import repeat

from loguru import logger

from src.constants import (EMPTY_QUESTION_MESSAGE, QUESTION_PREVIEW_MESSAGE,
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
        full_question = self.user.get('current_question')
        question_text = '\n'.join(full_question['text'])
        return question_text

    @property
    def current_question(self):
        """
        Get current question full message.
        This format contains extra information to be used in the preview.
        """
        question_formatted_text = QUESTION_PREVIEW_MESSAGE.format(question=self.question)
        return question_formatted_text

    def update_current_question(self, message):
        """
        In ask_question state, the user can send a question in multiple messages.
        In each message, we update the current question with the message recieved.
        """
        # if content is text, we store its html version to keep styles (bold, italic, etc.)
        if message.content_type == 'text':
            content = message.html_text
        else:
            # If content is a file, its file_id, mimetype, etc is saved in database for later use
            # Note that if content is a list, the last one has the highest quality
            content = getattr(message, message.content_type)
            content = vars(content[-1]) if isinstance(content, list) else vars(content)

        # Save file
        self.db.users.update_one({'chat.id': message.chat.id}, {
            '$push': {f'current_question.{message.content_type}': content}
        })

    def persist_question(self):
        """
        Save question to database.
        """
        logger.info('Save question to database...')
        if not self.user.get('current_question', {}).get('text'):
            self.send_message(EMPTY_QUESTION_MESSAGE)
            return False

        self.db.questions.insert_one({
            'chat_id': self.chat_id,
            'question': self.user.get('current_question', None),
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

    def reset(self):
        """
        Reset user state and data.
        """
        logger.info('Reset user data.')
        self.db.users.update_one(
            {'chat.id': self.chat_id},
            {'$set': {'state': states.main}, '$unset': {'current_question': 1}}
        )

if __name__ == '__main__':
    u = User(chat_id=371998922)
    print(u.state)
