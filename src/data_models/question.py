from src.constants import inline_keys, post_status
from src.utils.keyboard import create_keyboard

from data_models.post import Post


class Question(Post):
    """
    Class to handle questions sent by the users.
    """
    def __init__(self, mongodb, stackbot, chat_id=None):
        super().__init__(mongodb, stackbot, chat_id=chat_id)
        self.emoji = ':red_question_mark:'

    def send(self, post_id):
        self.send_to_all(post_id)

    def get_actions_keyboard(self, post_id, chat_id):
        keys, owner = super().get_actions_keys_and_owner(post_id, chat_id)
        if owner != chat_id:
            keys.append(inline_keys.answer)

        reply_markup = create_keyboard(*keys, is_inline=True)
        return reply_markup
