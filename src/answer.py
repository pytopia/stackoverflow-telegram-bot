from src.constants import inline_keys
from src.post import Post
from src.utils.keyboard import create_keyboard
from bson.objectid import ObjectId


class Answer(Post):
    def __init__(self, mongodb, stackbot):
        super().__init__(mongodb, stackbot)
        self.emoji = ':bright_button:'

    def submit(self, chat_id):
        post = super().submit(chat_id)

        # Send to the user who asked question
        question_owner = self.db.users.find_one({'chat.id': post['chat']['id']})
        self.send_to_one(post['_id'], question_owner['chat']['id'])

    def get_actions_keyboard(self, post_id, chat_id):
        answer = self.collection.find_one({'_id': post_id})
        answer_owner_chat_id = answer['chat']['id']

        question = self.db.question.find_one({'_id': ObjectId(answer['question_id'])})
        question_owner_chat_id = question['chat']['id']

        keys = [inline_keys.back]
        if chat_id == answer_owner_chat_id:
            keys.extend([inline_keys.edit, inline_keys.delete])

        if chat_id == question_owner_chat_id:
            keys.append(inline_keys.accept)

        reply_markup = create_keyboard(*keys, is_inline=True)
        return reply_markup
