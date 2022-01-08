import emoji
from loguru import logger
from telebot import types


def create_keyboard(
    *keys,
    reply_row_width=2, inline_row_width=4,
    resize_keyboard=True, is_inline=False, callback_data=None
):
    from src.constants import inline_keys
    from src.constants import inline_keys_groups
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

        sort_by_array = [inline_keys_groups.get(callback, ind + 100) for ind, callback in enumerate(callback_data)]
        sorted_array = sorted(zip(sort_by_array, keys, callback_data), key=lambda x: x[0])

        old_value = sorted_array[0][0]
        buttons = []
        markup = types.InlineKeyboardMarkup(row_width=inline_row_width)

        for sort_by, key, callback in sorted_array:
            if sort_by - old_value >= 10:
                markup.add(*buttons)
                buttons = []

            old_value = sort_by
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
