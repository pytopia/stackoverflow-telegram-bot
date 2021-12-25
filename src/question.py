import concurrent.futures
from itertools import repeat

from bson.objectid import ObjectId

import constants
from src.constants import inline_keys, question_status
from src.utils.common import human_readable_size
from src.utils.keyboard import create_keyboard


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
            content = {'text': message.html_text}
        else:
            # If content is a file, its file_id, mimetype, etc is saved in database for later use
            # Note that if content is a list, the last one has the highest quality
            content = getattr(message, message.content_type)
            content = vars(content[-1]) if isinstance(content, list) else vars(content)
        content['content_type'] = message.content_type

        # Save
        output = self.db.questions.update_one({'chat.id': message.chat.id, 'status': question_status.PREP}, {
            '$push': {f'content': content},
            '$set': {'date': message.date},
        }, upsert=True)

        _id = output.upserted_id or self.db.questions.find_one({'chat.id': message.chat.id, 'status': question_status.PREP})['_id']
        return _id

    def save(self, question_id: str):
        self.db.questions.update_one({'_id': question_id}, {'$set': {'status': question_status.SENT}})

    def send_to_one(self, question_id: str, chat_id: str, preview: bool = False):
        question_keyboard = self.get_quesiton_keyboard(question_id)
        question_text = self.get_quesiton_text(question_id)

        # Preview to user mode or send to other users
        if preview:
            question_formatted_text = constants.QUESTION_PREVIEW_MESSAGE.format(question=question_text)
        else:
            question_formatted_text = constants.SEND_QUESTION_TO_ALL_MESSAGE.format(
                from_user=chat_id, question=question_text
            )
        self.stackbot.send_message(chat_id=chat_id, text=question_formatted_text, reply_markup=question_keyboard)

    def send_to_all(self, question_id: str):
        chat_ids = map(lambda user: user['chat']['id'], self.db.users.find())
        with concurrent.futures.ThreadPoolExecutor() as executor:
            executor.map(self.send_to_one, repeat(question_id), chat_ids)

    def get_quesiton_text(self, question_id):
        question = self.db.questions.find_one({'_id': ObjectId(question_id)})
        question_text = ""
        for content in question['content']:
            if content['content_type'] == 'text':
                question_text += f"{content['text']}\n"

        # Empty question text is allowed
        if not question_text:
            question_text = constants.EMPTY_QUESTION_TEXT_MESSAGE

        return question_text

    def get_quesiton_keyboard(self, question_id):
        question = self.db.questions.find_one({'_id': ObjectId(question_id)})

        keys, callback_data = [], []
        question_keyboard = None
        for content in question['content']:
            if content['content_type'] != 'text':
                file_name = content.get('file_name') or content['content_type']
                file_size = human_readable_size(content['file_size'])
                keys.append(f"{file_name} - {file_size}")
                callback_data.append(content['file_unique_id'])

        # Create keyboard if any file is attached
        if keys:
            keys.append(inline_keys.actions)
            callback_data.append(str(question_id))

            question_keyboard = create_keyboard(*keys, callback_data=callback_data, is_inline=True)

        return question_keyboard
