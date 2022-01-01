import emoji
from loguru import logger
from telebot import types


def create_keyboard(*keys, reply_row_width=2, inline_row_width=3, resize_keyboard=True, is_inline=False, callback_data=None):
    from src.constants import inline_keys
    """
    Create a keyboard with buttons.

    :param keys: List of buttons
    :param row_width: Number of buttons in a row.
    :param resize_keyboard: Resize keyboard to small ones (works with reply keys only, not inline keys).
    :param is_inline: If True, create inline keyboard.
    :param callback_data: If not None, use keys text as callback data.
    """
    if callback_data and len(keys) != len(callback_data):
        logger.warning('Callback data length is not equal to keys length. Some keys will be missing.')

    keys = list(keys)

    if is_inline:
        # Set callback data to keys text
        if callback_data is None:
            callback_data = keys

        # Create inline keyboard
        markup = types.InlineKeyboardMarkup()
        buttons = []
        for ind, (key, callback) in enumerate(zip(keys, callback_data)):
            if key in [inline_keys.prev_post, inline_keys.first_page]:
                break

            key = emoji.emojize(key)
            button = types.InlineKeyboardButton(key, callback_data=callback)
            buttons.append(button)

            if (ind + 1) % inline_row_width == 0:
                markup.add(*buttons)
                buttons = []
        else:
            markup.add(*buttons)
            return markup

        # Add next and previous buttons
        markup.add(*buttons)
        buttons = []
        for key, callback in zip(keys[ind:], callback_data[ind:]):
            key = emoji.emojize(key)
            button = types.InlineKeyboardButton(key, callback_data=callback)
            buttons.append(button)
        markup.add(*buttons)
        return markup

    else:
        # create reply keyboard
        keys = list(map(emoji.emojize, keys))
        markup = types.ReplyKeyboardMarkup(
            row_width=reply_row_width,
            resize_keyboard=resize_keyboard
        )
        buttons = map(types.KeyboardButton, keys)
        markup.add(*buttons)
        return markup
