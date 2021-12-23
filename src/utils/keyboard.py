from telebot import types
import emoji
from functools import partial


def create_keyboard(*keys, row_width=2, resize_keyboard=True, is_inline=False, callback_data=None):
    """
    Create a keyboard from a list of keys.

    Example:
        keys = ['a', 'b', 'c', 'd']
    """
    keys = map(emoji.emojize, keys)

    if is_inline:
        markup = types.InlineKeyboardMarkup(row_width=row_width)
        buttons = []
        for key, callback in zip(keys, callback_data):
            button = types.InlineKeyboardButton(key, callback_data=callback)
            buttons.append(button)
    else:
        markup = types.ReplyKeyboardMarkup(
            row_width=row_width,
            resize_keyboard=resize_keyboard
        )
        buttons = map(types.KeyboardButton, keys)

    markup.add(*buttons)
    return markup
