
import emoji
from src import constants
from src.bot import bot
from src.constants import (DELETE_USER_MESSAGES_AFTER_TIME, keyboards, keys,
                           post_status, post_type, states)
from src.user import User


def register_message_handlers(self):
    @self.bot.middleware_handler(update_types=['message'])
    def init_message_handler(bot_instance, message):
        """
        Initialize user to use in other message handlers.

        1. Get user object.
        2. Demojize message text.
        """
        # Getting updated user before message reaches any other handler
        self.user = User(
            chat_id=message.chat.id, first_name=message.chat.first_name,
            mongodb=self.db, stackbot=self,
        )

        # Register user if not exists
        if not self.user.exists():
            self.user.register(message)

        # Demojize text
        if message.content_type == 'text':
            message.text = emoji.demojize(message.text)

        # Auto delete user message to keep the bot clean
        self.queue_delete_message(message.chat.id, message.message_id, DELETE_USER_MESSAGES_AFTER_TIME)

    @self.bot.message_handler(text=[keys.ask_question])
    def ask_question(message):
        """
        Users starts sending question.

        1. Update state.
        2. Send how to ask a question guide.
        3. Send start typing message.
        """
        if not self.user.state == states.MAIN:
            return

        self.user.update_state(states.ASK_QUESTION)
        self.user.send_message(constants.HOW_TO_ASK_QUESTION_GUIDE, reply_markup=keyboards.send_post)
        self.user.send_message(constants.POST_START_MESSAGE.format(
            first_name=self.user.first_name, post_type='question'
        ))

    @self.bot.message_handler(text=[keys.cancel])
    def cancel(message):
        """
        User cancels sending a post.

        1. Reset user state and data.
        2. Send cancel message.
        3. Delete previous bot messages.
        """
        self.user.clean_preview()
        self.user.send_message(constants.CANCEL_MESSAGE, reply_markup=keyboards.main)
        self.user.reset()

    @self.bot.message_handler(text=[keys.send_post])
    def send_post(message):
        """
        User sends a post.

        1. Submit post to database.
        2. Check if post is not empty.
        3. Send post to the relevant audience.
        4. Reset user state and data.
        5. Delete previous bot messages.
        """
        post_id = self.user.post.submit()
        if not post_id:
            self.user.send_message(constants.EMPTY_POST_MESSAGE)
            return

        self.user.post.post_id = post_id
        self.user.post.send()
        self.user.send_message(
            text=constants.POST_OPEN_SUCCESS_MESSAGE.format(
                post_type=self.user.post.post_type.title(),
            ),
            reply_markup=keyboards.main
        )

        # Reset user state and data
        self.user.clean_preview()
        self.user.reset()

    @self.bot.message_handler(text=[keys.settings])
    def settings(message):
        """
        User cancels sending a post.

        1. Send Settings Message.
        """
        if self.user.state != states.MAIN:
            return

        self.user.send_message(text=self.get_settings_text(), reply_markup=self.get_settings_keyboard())

    @self.bot.message_handler(text=[keys.search_questions])
    def search_questions(message):
        """
        User cancels sending a post.

        1. Send Settings Message.
        """
        if self.user.state != states.MAIN:
            return

        # we should change the post_id for the buttons
        gallery_filters = {'type': post_type.QUESTION, 'status': post_status.OPEN}
        posts = self.db.post.find(gallery_filters).sort('date', -1)
        num_posts = self.db.post.count_documents(gallery_filters)
        next_post = next(posts)

        is_gallery = True if num_posts > 1 else False
        gallery_message = self.send_gallery(
            chat_id=message.chat.id, post_id=next_post['_id'],
            is_gallery=is_gallery, gallery_filters=gallery_filters
        )

        self.db.callback_data.update_one(
            {'chat_id': gallery_message.chat.id, 'message_id': gallery_message.message_id},
            {'$set': {'gallery_filters': gallery_filters}},
            upsert=True,
        )

    # Handles all other messages with the supported content_types
    @bot.message_handler(content_types=constants.SUPPORTED_CONTENT_TYPES)
    def echo(message):
        """
        Respond to user according to the current user state.

        1. Check if message content is supported by the bot for the current post type (Question, Answer, Comment).
        2. Update user post data in database with the new message content.
        3. Send message preview to the user.
        4. Delete previous bot messages.
        """
        if self.user.state not in [states.ASK_QUESTION, states.ANSWER_QUESTION, states.COMMENT_POST]:
            return

        supported_contents = self.user.post.supported_content_types
        if message.content_type not in supported_contents:
            self.user.send_message(
                constants.UNSUPPORTED_CONTENT_TYPE_MESSAGE.format(supported_contents=' '.join(supported_contents))
            )
            return

        self.user.post.update(message, replied_to_post_id=self.user.tracker.get('replied_to_post_id'))
        new_preview_message = self.user.post.send_to_one(chat_id=message.chat.id, preview=True)
        self.user.clean_preview(new_preview_message.message_id)
