from src.constants import inline_keys, post_status
from src.utils.keyboard import create_keyboard

from data_models.post import Post


class Question(Post):
    """
    Class to handle questions sent by the users.
    """
    def __init__(self, mongodb, stackbot, chat_id=None):
        super().__init__(mongodb, stackbot)
        self.emoji = ':red_question_mark:'

    def submit(self):
        post = super().submit()
        if not post:
            return

        self.send_to_all(post['_id'])
        return post

    def get_actions_keyboard(self, post_id, chat_id):
        question = self.collection.find_one({'_id': post_id})
        question_owner_chat_id = question['chat']['id']

        keys = [inline_keys.back, inline_keys.answer, inline_keys.follow, inline_keys.comment]
        if chat_id == question_owner_chat_id:
            current_status = question['status']
            if current_status == post_status.OPEN:
                keys.append(inline_keys.close)
            else:
                keys.append(inline_keys.open)
            keys.append(inline_keys.edit)

        reply_markup = create_keyboard(*keys, is_inline=True)
        return reply_markup
