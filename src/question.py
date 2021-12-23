import concurrent.futures

import constants
from src.constants import question_status
from src.utils.common import human_readable_size
from src.utils.keyboard import create_keyboard
from itertools import repeat


class Question:
    def __init__(self, mongodb, stackbot):
        self.db = mongodb
        self.stackbot = stackbot

    def update(self, message):
        """
        In ask_question state, the user can send a question in multiple messages.
        In each message, we update the current question with the message recieved.
        """
        # If content is text, we store its html version to keep styles (bold, italic, etc.)
        if message.content_type == 'text':
            content = message.html_text
        else:
            # If content is a file, its file_id, mimetype, etc is saved in database for later use
            # Note that if content is a list, the last one has the highest quality
            content = getattr(message, message.content_type)
            content = vars(content[-1]) if isinstance(content, list) else vars(content)

        # Save
        output = self.db.questions.update_one({'chat.id': message.chat.id, 'status': question_status.PREP}, {
            '$push': {f'content.{message.content_type}': content},
            '$set': {'date': message.date},
        }, upsert=True)

        _id = output.upserted_id or self.db.questions.find_one({'chat.id': message.chat.id, 'status': question_status.PREP})['_id']
        return _id

    def save(self, question_id: str):
        self.db.questions.update_one({'_id': question_id}, {'$set': {'status': question_status.SENT}})

    def send_to_one(self, question_id: str, chat_id: str, preview: bool = False):
        question = self.db.questions.find_one({'_id': question_id})
        if not question['content'].get('text'):
            question_text = constants.EMPTY_QUESTION_TEXT_MESSAGE
        else:
            question_text = '\n'.join(question['content']['text'])

        # Create keys and keyboard
        keys, callback_data = [], []
        keyboard = None
        for content_type in constants.SUPPORTED_CONTENT_TYPES:
            if content_type == 'text' or not question['content'].get(content_type):
                continue

            for content in question['content'][content_type]:
                file_name = content.get('file_name') or content_type
                file_size = human_readable_size(content['file_size'])
                keys.append(f"{file_name} - {file_size}")
                callback_data.append(content['file_unique_id'])

        if keys:
            keyboard = create_keyboard(*keys, callback_data=callback_data, is_inline=True)

        # Preview to user mode or send to other users
        if preview:
            question_formatted_text = constants.QUESTION_PREVIEW_MESSAGE.format(question=question_text)
        else:
            question_formatted_text = constants.SEND_QUESTION_TO_ALL_MESSAGE.format(
                from_user=chat_id, question=question_text
            )
        self.stackbot.send_message(chat_id=chat_id, text=question_formatted_text, reply_markup=keyboard)

    def send_to_all(self, question_id: str):
        chat_ids = map(lambda user: user['chat']['id'], self.db.users.find())
        with concurrent.futures.ThreadPoolExecutor() as executor:
            executor.map(self.send_to_one, repeat(question_id), chat_ids)
