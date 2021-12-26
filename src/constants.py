from types import SimpleNamespace

from src.data import DATA_DIR
from src.utils.io import read_file
from src.utils.keyboard import create_keyboard

keys = SimpleNamespace(
    settings=':gear: Settings',
    cancel=':cross_mark: Cancel',
    back=':arrow_left: Back',
    next=':arrow_right: Next',
    add=':heavy_plus_sign: Add',
    save=':check_mark_button: Save',
    yes=':white_check_mark: Yes',
    no=':negative_squared_cross_mark: No',
    ask_question=':red_question_mark: Ask a Question',
    send_question=':envelope_with_arrow: Send Question',
    send_answer=':envelope_with_arrow: Send Answer',
)

inline_keys = SimpleNamespace(
    actions='Actions »',
    back='« Back',
    answer=':bright_button: Answer',
    follow=':plus: Follow',
    unfollow=':minus: Unfollow',
    like=':red_heart: Like',
    accept=':check_mark_button: Accept',
    comment=':speech_balloon: Comment',
    delete=':wastebasket: Delete',
    edit=':pencil: Edit',
)

keyboards = SimpleNamespace(
    main=create_keyboard(keys.ask_question, keys.settings),
    ask_question=create_keyboard(keys.cancel, keys.send_question),
    answer_question=create_keyboard(keys.cancel, keys.send_answer),
)

states = SimpleNamespace(
    MAIN='MAIN',
    ASK_QUESTION='ASK_QUESTION',
    ANSWER_QUESTION='ANSWER_QUESTION',
)

post_status = SimpleNamespace(
    PREP='in_prep',
    DRAFT='draft',
    CLOSED='closed',
    OPEN='open',
)

SUPPORTED_CONTENT_TYPES = ['text', 'photo', 'audio', 'document', 'video', 'voice', 'video_note']
CALLBACK_LENGTH_LIMIT = 64

# Constant Text Messages
# General Messages
HOW_TO_ASK_QUESTION_GUIDE = read_file(DATA_DIR / 'guide.html')
ASK_QUESTION_START_MESSAGE = (
    # first_name is filled later
    ":pencil: <strong>{first_name}</strong>, send your question here.\n"
    f"When done, click <strong>{keys.send_question}</strong>."
)

WELCOME_MESSAGE = "Hey <strong>{first_name}</strong>!"
POST_OPEN_SUCCESS_MESSAGE = ":check_mark_button: {post_type} sent successfully."
CANCEL_MESSAGE = ':cross_mark: Canceled.'

# Question Templates
POST_PREVIEW_MESSAGE = (
    ':pencil: <strong>{post_type} Preview</strong>\n\n'
    '{post_text}\n'  # Question is filled later
    f'{"_" * 10}\n'
    f'When done, click <strong>send</strong>.'
)

SEND_POST_TO_ALL_MESSAGE = (
    ':bust_in_silhouette: From: {from_user}\n'
    '{emoji} <strong>New {post_type}</strong>\n\n'
    '{post_text}'
)

SEND_TO_ALL_SUCCESS_MESSAGE = ':check_mark_button: Question sent successfully to all users.'

EMPTY_POST_MESSAGE = ':cross_mark: {post_type} is empty!'

EMPTY_QUESTION_TEXT_MESSAGE = ':warning: Empty Question'
FILE_NOT_FOUND_ERROR_MESSAGE = ':cross_mark: File not found!'

ANSWER_QUESTION_START_MESSAGE = ':pencil: <strong>{first_name}</strong>, send your answer here:\n\n'
