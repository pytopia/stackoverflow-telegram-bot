from abc import ABC, abstractclassmethod

from src.constants import SETTINGS_START_MESSAGE, inline_keys
from src.utils.keyboard import create_keyboard


class BaseHandler(ABC):
    """
    Base class for all telebot handlers.
    """
    def __init__(self, stack, db):
        self.stack = stack
        self.db = db

    @abstractclassmethod
    def register(self):
        """
        Register telebot handlers.
        """

    def get_settings_keyboard(self):
        """
        Returns settings main menu keyboard.
        """
        muted_bot = self.stack.user.settings.get('muted_bot')
        if muted_bot:
            keys = [inline_keys.change_identity, inline_keys.unmute]
        else:
            keys = [inline_keys.change_identity, inline_keys.mute]

        return create_keyboard(*keys, is_inline=True)

    def get_settings_text(self):
        """
        Returns settings text message.
        """
        text = SETTINGS_START_MESSAGE.format(
            first_name=self.stack.user.first_name,
            username=self.stack.user.username,
            identity=self.stack.user.identity,
        )
        return text
