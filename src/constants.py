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
    search_questions=':magnifying_glass_tilted_right: Search Questions',
)

inline_keys = SimpleNamespace(
    actions='Actions »',
    back='« Back',
    answer=':bright_button: Answer',
    follow=':plus: Follow',
    unfollow=':minus: Unfollow',
    like=':red_heart:',
    unlike=':white_heart:',
    accept=':check_mark_button: Accept',
    comment=':speech_balloon: Comment',
    delete=':wastebasket: Delete',
    undelete=':recycling_symbol: Undelete',
    open=':green_circle: Open',
    close=':red_circle: Close',
    edit=':pencil: Edit',
    change_identity=':smiling_face_with_sunglasses: Change Identity',
    ananymous=':smiling_face_with_sunglasses: Ananymous',
    first_name=':bust_in_silhouette: First Name',
    username=':bust_in_silhouette: Username',
    alias=':smiling_face_with_sunglasses: Alias',
    mute=':muted_speaker: Mute Bot',
    unmute=':speaker_high_volume: Unmute Bot',
    show_comments=':right_anger_bubble:',
    show_answers=':dim_button:',
    original_post=':BACK_arrow:',
    next_post='»',
    prev_post='«',
    last_page=':white_small_square:',
    first_page=':white_small_square:'
)

keyboards = SimpleNamespace(
    main=create_keyboard(keys.ask_question, keys.search_questions, keys.settings),
    send_post=create_keyboard(keys.cancel, keys.send_post),
)

states = SimpleNamespace(
    MAIN='MAIN',
    ASK_QUESTION='ASK_QUESTION',
    ANSWER_QUESTION='ANSWER_QUESTION',
    COMMENT_POST='COMMENT_POST',
    SEARCH_QUESTIONS='SEARCH_QUESTIONS',
)

post_status = SimpleNamespace(
    PREP=':yellow_circle: Typing...',
    DRAFT=':white_circle: Draft',
    CLOSED=':red_circle: Closed',
    OPEN=':green_circle: Open',
    DELETED=':wastebasket: Deleted',
)

post_type = SimpleNamespace(
    QUESTION='question',
    ANSWER='answer',
    COMMENT='comment',
)

user_identity = SimpleNamespace(
    ANANYMOUS=':smiling_face_with_sunglasses: Ananymous',
    FIRST_NAME=':bust_in_silhouette: First Name',
    USERNAME=':bust_in_silhouette: Username',
    ALIAS=':smiling_face_with_sunglasses: Alias',
)

SUPPORTED_CONTENT_TYPES = ['text', 'photo', 'audio', 'document', 'video', 'voice', 'video_note']
EMOJI = {
    post_type.QUESTION: ':red_question_mark:',
    post_type.ANSWER: ':bright_button:',
    post_type.COMMENT: ':speech_balloon:',
}

OPEN_POST_ONLY_ACITONS = [
    inline_keys.comment, inline_keys.edit, inline_keys.answer,
]

# Auto delete user and bot messages after a period of time
DELETE_BOT_MESSAGES_AFTER_TIME = 10
DELETE_USER_MESSAGES_AFTER_TIME = 10

# Constant Text Messages
# General Templates
HOW_TO_ASK_QUESTION_GUIDE = read_file(DATA_DIR / 'guide.html')
WELCOME_MESSAGE = "Hey <strong>{first_name}</strong>!"
CANCEL_MESSAGE = ':cross_mark: Canceled.'
IDENTITY_TYPE_NOT_SET_WARNING = (
    ':warning: <strong>{identity_type}</strong> is not set. '
    'Please set it in your settings or Telegram.'
)

# Post Templates
POST_OPEN_SUCCESS_MESSAGE = ":check_mark_button: {post_type} sent successfully."
EMPTY_POST_MESSAGE = ':cross_mark: Empty!'
POST_PREVIEW_MESSAGE = (
    ':pencil: <strong>{post_type} Preview</strong>\n\n'
    '{post_text}\n'
    f'{"_" * 10}\n'
    f'When done, click <strong>send</strong>.'
)
SEND_POST_TO_ALL_MESSAGE = (
    '{emoji} <strong>New {post_type}</strong>\n'
    ':bust_in_silhouette: From: {from_user}\n'
    '{post_status}\n'
    '\n'
    '{post_text}\n'
    '\n\n'
    ':calendar: <code>{date}</code>\n'
    ':ID_button: <code>{post_id}</code>'
)
POST_START_MESSAGE = (
    ":pencil: <strong>{first_name}</strong>, send your <strong>{post_type}</strong> here.\n\n"
    f"When done, click {keys.send_post}."
)

# Question Templates
EMPTY_QUESTION_TEXT_MESSAGE = ':warning: Empty Question'

# File Templates
FILE_NOT_FOUND_ERROR_MESSAGE = ':cross_mark: File not found!'
UNSUPPORTED_CONTENT_TYPE_MESSAGE = (
    ':cross_mark: Unsupported content type.\n\n'
    ':safety_pin: Allowed types: {supported_contents}'
)

# Settings Templates
SETTINGS_START_MESSAGE = (
    ':gear: <strong>Settings</strong>\n'
    ':bust_in_silhouette: {first_name} ({username})\n\n'

    ':smiling_face_with_sunglasses: Identity: <strong>{identity}</strong>\n\n'
)

# Gallery Templates
GALLERY_NO_POSTS_MESSAGE = ':red_exclamation_mark: No {post_type} found.'
