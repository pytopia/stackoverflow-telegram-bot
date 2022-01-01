from src.constants import inline_keys, post_status
from src.data_models.base import BasePost
from src.utils.keyboard import create_keyboard
from telebot import types


class Question(BasePost):
    """
    Class to handle questions sent by the users.
    """
    def send(self) -> dict:
        """Send question to the right audience.
        We send questions to all users.

        :return: The question post.
        """
        return self.send_to_all()

    def get_actions_keyboard(self) -> types.InlineKeyboardMarkup:
        """
        Get question section actions keyboard.

        Keyboard changes depending on the user's role.
        If the user is the owner of the question, he can't send answer for it, but others can.
        """
        keys, owner = super().get_actions_keys_and_owner()
        if owner != self.chat_id:
            keys.append(inline_keys.answer)

        # if post is closed, remove open post only actions from keyboard
        if self.post_status != post_status.OPEN:
            keys = self.remove_closed_post_actions(keys)

        reply_markup = create_keyboard(*keys, is_inline=True)
        return reply_markup
