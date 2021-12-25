import emoji
from telebot import types


def create_keyboard(*keys, row_width=2, resize_keyboard=True, is_inline=False, callback_data=None):
    """
    Create a keyboard with buttons.

    :param keys: List of buttons
    :param row_width: Number of buttons in a row.
    :param resize_keyboard: Resize keyboard to small ones (works with reply keys only, not inline keys).
    :param is_inline: If True, create inline keyboard.
    :param callback_data: If not None, use keys text as callback data.
    """
    keys = list(map(emoji.emojize, keys))

    if is_inline:
        # create inline keyboard
        markup = types.InlineKeyboardMarkup(row_width=row_width)

        # set callback data to keys text
        if callback_data is None:
            callback_data = keys

        buttons = []
        for key, callback in zip(keys, callback_data):
            button = types.InlineKeyboardButton(key, callback_data=callback)
            buttons.append(button)
    else:
        # create reply keyboard
        markup = types.ReplyKeyboardMarkup(
            row_width=row_width,
            resize_keyboard=resize_keyboard
        )
        buttons = map(types.KeyboardButton, keys)

    markup.add(*buttons)
    return markup
