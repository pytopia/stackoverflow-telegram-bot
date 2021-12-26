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
    send_post=':envelope_with_arrow: Send',
    send_answer=':envelope_with_arrow: Send Answer',
)

inline_keys = SimpleNamespace(
    actions='Actions »',
    back='« Back',
    answer=':bright_button: Answer',
    follow=':plus: Follow',
    unfollow=':minus: Unfollow',
    like=':red_heart: Like',
    unlike=':white_heart: Like',
    accept=':check_mark_button: Accept',
    comment=':speech_balloon: Comment',
    delete=':wastebasket: Delete',
    open=':green_circle: Open',
    close=':red_circle: Close',
    edit=':pencil: Edit',
)

keyboards = SimpleNamespace(
    main=create_keyboard(keys.ask_question, keys.settings),
    send_post=create_keyboard(keys.cancel, keys.send_post),
)

states = SimpleNamespace(
    MAIN='MAIN',
    ASK_QUESTION='ASK_QUESTION',
    ANSWER_QUESTION='ANSWER_QUESTION',
    COMMENT_POST='COMMENT_POST',
)

post_status = SimpleNamespace(
    PREP=':white_circle: In Preparation',
    DRAFT=':yello_circle: Draft',
    CLOSED=':red_circle: Closed',
    OPEN=':green_circle: Open',
)

SUPPORTED_CONTENT_TYPES = ['text', 'photo', 'audio', 'document', 'video', 'voice', 'video_note']

# Constant Text Messages
# General Templates
HOW_TO_ASK_QUESTION_GUIDE = read_file(DATA_DIR / 'guide.html')
WELCOME_MESSAGE = "Hey <strong>{first_name}</strong>!"
CANCEL_MESSAGE = ':cross_mark: Canceled.'

# Post Templates
POST_OPEN_SUCCESS_MESSAGE = ":check_mark_button: {post_type} sent successfully."
EMPTY_POST_MESSAGE = ':cross_mark: {post_type} is empty!'
POST_PREVIEW_MESSAGE = (
    ':pencil: <strong>{post_type} Preview</strong>\n\n'
    '{post_text}\n'
    f'{"_" * 10}\n'
    f'When done, click <strong>send</strong>.'
)
SEND_POST_TO_ALL_MESSAGE = (
    '{emoji} <strong>New {post_type}</strong>\n'
    ':bust_in_silhouette: From: {from_user}\n'
    '{post_status}\n\n'
    '{post_text}'
)
POST_START_MESSAGE = (
    ":pencil: <strong>{first_name}</strong>, send your {post_type} here.\n"
    f"When done, click <strong>{keys.send_post}</strong>."
)

# Question Templates
EMPTY_QUESTION_TEXT_MESSAGE = ':warning: Empty Question'

# File Templates
FILE_NOT_FOUND_ERROR_MESSAGE = ':cross_mark: File not found!'
