import concurrent.futures
from itertools import repeat

from loguru import logger

from src import constants
from src.constants import states
from src.utils.common import human_readable_size
from src.utils.keyboard import create_keyboard


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
    def current_question(self):
        """
        Get current question full message.
        This format contains extra information to be used in the preview.
        """
        current_question = self.user['current_question']
        if not current_question.get('text'):
            question_text = constants.EMPTY_QUESTION_TEXT_MESSAGE
        else:
            question_text = '\n'.join(current_question['text'])

        keys, callback_data = [], []
        keyboard = None
        for content_type in constants.SUPPORTED_CONTENT_TYPES:
            if content_type == 'text' or not current_question.get(content_type):
                continue

            for content in current_question[content_type]:
                file_name = content.get('file_name') or content_type
                file_size = human_readable_size(content['file_size'])
                keys.append(f"{file_name} - {file_size}")
                callback_data.append(content['file_unique_id'])

        # Create keyboard for files
        if keys:
            keyboard = create_keyboard(*keys, callback_data=callback_data, is_inline=True)

        return question_text, keyboard

    def preview_current_question(self):
        question_text, question_keyboard = self.current_question
        question_formatted_text = constants.QUESTION_PREVIEW_MESSAGE.format(question=question_text)
        return question_formatted_text, question_keyboard

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
            self.send_message(constants.EMPTY_QUESTION_MESSAGE)
            return False

        _id = self.db.questions.insert_one({
            'chat_id': self.chat_id,
            'question': self.user.get('current_question', None),
            'date': self.message.date,
        })

        return _id.inserted_id

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
        msg_text = constants.SEND_QUESTION_TO_ALL_MESSAGE.format(from_user=from_user, question=self.current_question)

        # Send to all users in parallel
        with concurrent.futures.ThreadPoolExecutor() as executor:
            executor.map(self.stackbot.send_message, self.db.users.distinct('chat.id'), repeat(msg_text))
        self.send_message(constants.SEND_TO_ALL_SUCCESS_MESSAGE)

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
