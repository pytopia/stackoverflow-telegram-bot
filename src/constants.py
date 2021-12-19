from types import SimpleNamespace

import emoji

from src.utils.keyboard import create_keyboard

keys = SimpleNamespace(
    settings=':gear: Settings',
    cancel=':cross_mark: Cancel',
    back=':arrow_left: Back',
    next=':arrow_right: Next',
    add=':heavy_plus_sign: Add',
    edit=':pencil: Edit',
    save=':check_mark_button: Save',
    delete=':wastebasket: Delete',
    yes=':white_check_mark: Yes',
    no=':negative_squared_cross_mark: No',
    ask_question=':red_question_mark: Ask a question',
    send_question=':envelope_with_arrow: Send questions',
)

keyboards = SimpleNamespace(
    main=create_keyboard(keys.ask_question, keys.settings),
    ask_question=create_keyboard(keys.cancel, keys.send_question),
)

states = SimpleNamespace(
    main='MAIN',
    ask_question='ASK_QUESTION',
)
