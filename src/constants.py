from types import SimpleNamespace

from src.data import DATA_DIR
from src.utils.io import read_file
from src.utils.keyboard import create_keyboard

keys = SimpleNamespace(
    settings=':gear: Settings',
    cancel=':cross_mark: Cancel',
    back=':BACK_arrow: Back',
    next=':arrow_right: Next',
    add=':heavy_plus_sign: Add',
    save=':check_mark_button: Save',
    yes=':white_check_mark: Yes',
    no=':negative_squared_cross_mark: No',
    ask_question=':red_question_mark: Ask a Question',
    send_post=':envelope_with_arrow: Send',
    send_answer=':envelope_with_arrow: Send Answer',
    search_questions=':magnifying_glass_tilted_right: Search Questions',
    my_data=':thought_balloon: My Data',
    my_questions=':red_question_mark: My Questions',
    my_answers=':bright_button: My Answers',
    my_comments=':speech_balloon: My Comments',
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
    unaccept=':red_exclamation_mark: Unaccept',
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
    original_post=':reverse_button: Main Post',
    next_post='»',
    prev_post='«',
    last_page=':white_small_square:',
    first_page=':white_small_square:',
    show_more=u'\u2193 Show More',
    show_less=u'\u2191 Show Less',
    export_gallery=':inbox_tray: Export'
)

keyboards = SimpleNamespace(
    main=create_keyboard(keys.ask_question, keys.search_questions, keys.my_data, keys.settings),
    send_post=create_keyboard(keys.cancel, keys.send_post),
    my_data=create_keyboard(keys.my_questions, keys.my_answers, keys.my_comments, keys.back, reply_row_width=3),
)

states = SimpleNamespace(
    MAIN='MAIN',
    ASK_QUESTION='ASK_QUESTION',
    ANSWER_QUESTION='ANSWER_QUESTION',
    COMMENT_POST='COMMENT_POST',
    SEARCH_QUESTIONS='SEARCH_QUESTIONS',
)

post_status = SimpleNamespace(
    # Answer Status
    ACCEPTED_ANSWER=':check_mark_button:',

    # General Status
    PREP=':yellow_circle: Typing...',
    DRAFT=':white_circle: Draft',
    CLOSED=':red_circle: Closed',
    OPEN=':green_circle: Open',
    DELETED=':wastebasket: Deleted',
    RESOLVED=':check_mark_button: Resolved'
)

post_types = SimpleNamespace(
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

post_text_length_button = SimpleNamespace(
    SHOW_MORE=inline_keys.show_more,
    SHOW_LESS=inline_keys.show_less,
)

SUPPORTED_CONTENT_TYPES = ['text', 'photo', 'audio', 'document', 'video', 'voice', 'video_note']
EMOJI = {
    post_types.QUESTION: ':red_question_mark:',
    post_types.ANSWER: ':bright_button:',
    post_types.COMMENT: ':speech_balloon:',
}

HTML_ICON = {
    post_types.QUESTION: '&#10067;',
    post_types.ANSWER: '&#11088;',
    post_types.COMMENT: '&#128172;',
}

OPEN_POST_ONLY_ACITONS = [
    inline_keys.comment, inline_keys.edit, inline_keys.answer,
]

# Message Limits

# Posts longer than this are not allowed
POST_CHAR_LIMIT = {
    post_types.QUESTION: 2500,
    post_types.ANSWER: 2500,
    post_types.COMMENT: 500,
}
ATTACHMENT_LIMIT = 3
MAX_NUMBER_OF_CHARACTERS_MESSAGE = (
    ':cross_mark: Max number of characters reached. '
    'You made {num_extra_characters} extra characters. '
    '<strong>Last message is ignored.</strong>'
)
MAX_NUMBER_OF_ATTACHMENTS_MESSAGE = (
    ':cross_mark: Max number of attachments reached. '
    f'You can have up to {ATTACHMENT_LIMIT} attachments only.'
)

MIN_POST_TEXT_LENGTH = 20
MIN_POST_TEXT_LENGTH_MESSAGE = f':cross_mark: Enter at least <code>{MIN_POST_TEXT_LENGTH}</code> characters.'

# This is used for show more button
MESSAGE_SPLIT_CHAR_LIMIT = 250


# Auto delete user and bot messages after a period of time
DELETE_BOT_MESSAGES_AFTER_TIME = 1
DELETE_USER_MESSAGES_AFTER_TIME = 1
DELETE_FILE_MESSAGES_AFTER_TIME = 1 * 60 * 60

# Constant Text Messages
# General Templates
HOW_TO_ASK_QUESTION_GUIDE = read_file(DATA_DIR / 'guide.html')
WELCOME_MESSAGE = "Hey <strong>{first_name}</strong>!"
CANCEL_MESSAGE = ':cross_mark: Canceled.'
IDENTITY_TYPE_NOT_SET_WARNING = (
    ':warning: <strong>{identity_type}</strong> is not set. '
    'Please set it in your settings or Telegram.'
)
MY_DATA_MESSAGE = ':thought_balloon: Select your data type from the menu:'
BACK_TO_HOME_MESSAGE = ':house: Back to Home'
NEW_ACCEPTED_ANSWER = ':check_mark_button: New accepted answer:'
USER_ANSWER_IS_ACCEPTED_MESSAGE = ':party_popper: Awesome! Your answer is accepted now.'

# Post Templates
POST_OPEN_SUCCESS_MESSAGE = ":check_mark_button: {post_type} sent successfully."
EMPTY_POST_MESSAGE = ':cross_mark: Empty!'
POST_PREVIEW_MESSAGE = (
    ':pencil: <strong>{post_type} Preview</strong>\n\n'
    '{post_text}\n'
    f'{"_" * 10}\n'
    f'When done, click <strong>{keys.send_post}</strong>.\n\n'
    ':memo: <code>{num_characters_left}</code> characters left.\n'
    ':ID_button: <code>{post_id}</code>'
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
    f"When done, click <strong>{keys.send_post}</strong>."
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
