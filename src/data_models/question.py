from src.constants import inline_keys
from src.utils.keyboard import create_keyboard
from telebot import types

from data_models.post import Post


class Question(Post):
    """
    Class to handle questions sent by the users.
    """
    def __init__(self, mongodb, stackbot, chat_id: str = None):
        super().__init__(mongodb, stackbot, chat_id=chat_id)
        self.emoji = ':red_question_mark:'

    def send(self, post_id: str) -> dict:
        """Send question to the right audience.
        We send questions to all users.

        :param post_id: ObjectId of the question post.
        :return: The question post.
        """
        return self.send_to_all(post_id)

    def get_actions_keyboard(self, post_id: str, chat_id: str) -> types.InlineKeyboardMarkup:
        """
        Get question section actions keyboard.

        Keyboard changes depending on the user's role.
        If the user is the owner of the question, he can't send answer for it, but others can.
        """
        keys, owner = super().get_actions_keys_and_owner(post_id, chat_id)
        if owner != chat_id:
            keys.append(inline_keys.answer)

        reply_markup = create_keyboard(*keys, is_inline=True)
        return reply_markup
