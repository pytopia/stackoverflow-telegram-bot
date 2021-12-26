from src.constants import inline_keys
from src.utils.keyboard import create_keyboard

from data_models.post import Post


class Question(Post):
    """
    Class to handle questions sent by the users.
    """
    def __init__(self, mongodb, stackbot):
        super().__init__(mongodb, stackbot)
        self.emoji = ':red_question_mark:'

    def submit(self, chat_id):
        post = super().submit(chat_id)
        self.send_to_all(post['_id'])

    def get_actions_keyboard(self, post_id, chat_id):
        question = self.collection.find_one({'_id': post_id})
        question_owner_chat_id = question['chat']['id']

        keys = [inline_keys.back, inline_keys.answer, inline_keys.follow, inline_keys.comment]
        if chat_id == question_owner_chat_id:
            keys.extend([inline_keys.delete, inline_keys.edit])

        reply_markup = create_keyboard(*keys, is_inline=True)
        return reply_markup
