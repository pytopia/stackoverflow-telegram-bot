
import emoji
from src import constants
from src.bot import bot
from src.constants import (DELETE_USER_MESSAGES_AFTER_TIME, keyboards, keys,
                           post_status, post_type, states)
from src.data_models.post import Post
from src.user import User


class MessageHandler:
    def __init__(self, stack):
        self.stack = stack

    def register(self):
        @self.stack.bot.middleware_handler(update_types=['message'])
        def init_message_handler(bot_instance, message):
            """
            Initialize user to use in other message handlers.

            1. Get user object.
            2. Demojize message text.
            """
            # Getting updated user before message reaches any other handler
            self.stack.user = User(
                chat_id=message.chat.id, first_name=message.chat.first_name,
                mongodb=self.stack.db, stackbot=self.stack,
            )

            # Register user if not exists
            if not self.stack.user.exists():
                self.stack.user.register(message)

            # Demojize text
            if message.content_type == 'text':
                message.text = emoji.demojize(message.text)

            # Auto delete user message to keep the bot clean
            self.stack.queue_delete_message(message.chat.id, message.message_id, DELETE_USER_MESSAGES_AFTER_TIME)

        @self.stack.bot.message_handler(text=[keys.ask_question])
        def ask_question(message):
            """
            Users starts sending question.

            1. Update state.
            2. Send how to ask a question guide.
            3. Send start typing message.
            """
            if not self.stack.user.state == states.MAIN:
                return

            self.stack.user.update_state(states.ASK_QUESTION)
            self.stack.user.send_message(constants.HOW_TO_ASK_QUESTION_GUIDE, reply_markup=keyboards.send_post)
            self.stack.user.send_message(constants.POST_START_MESSAGE.format(
                first_name=self.stack.user.first_name, post_type='question'
            ))

        @self.stack.bot.message_handler(text=[keys.cancel])
        def cancel(message):
            """
            User cancels sending a post.

            1. Reset user state and data.
            2. Send cancel message.
            3. Delete previous bot messages.
            """
            self.stack.user.clean_preview()
            self.stack.user.send_message(constants.CANCEL_MESSAGE, reply_markup=keyboards.main)
            self.stack.user.reset()

        @self.stack.bot.message_handler(text=[keys.send_post])
        def send_post(message):
            """
            User sends a post.

            1. Submit post to database.
            2. Check if post is not empty.
            3. Send post to the relevant audience.
            4. Reset user state and data.
            5. Delete previous bot messages.
            """
            post_id = self.stack.user.post.submit()
            if not post_id:
                self.stack.user.send_message(constants.EMPTY_POST_MESSAGE)
                return

            self.stack.user.post.post_id = post_id
            self.stack.user.post.send()
            self.stack.user.send_message(
                text=constants.POST_OPEN_SUCCESS_MESSAGE.format(
                    post_type=self.stack.user.post.post_type.title(),
                ),
                reply_markup=keyboards.main
            )

            # Reset user state and data
            self.stack.user.clean_preview()
            self.stack.user.reset()

        @self.stack.bot.message_handler(text=[keys.settings])
        def settings(message):
            """
            User cancels sending a post.

            1. Send Settings Message.
            """
            if self.stack.user.state != states.MAIN:
                return

            self.stack.user.send_message(self.stack.get_settings_text(), self.stack.get_settings_keyboard())

        @self.stack.bot.message_handler(text=[keys.search_questions])
        def search_questions(message):
            """
            User cancels sending a post.

            1. Send Settings Message.
            """
            if self.stack.user.state != states.MAIN:
                return

            # we should change the post_id for the buttons
            gallery_filters = {'type': post_type.QUESTION, 'status': post_status.OPEN}
            posts = self.stack.db.post.find(gallery_filters).sort('date', -1)
            num_posts = self.stack.db.post.count_documents(gallery_filters)
            next_post = next(posts)

            is_gallery = True if num_posts > 1 else False
            gallery_message = self.send_gallery(
                chat_id=message.chat.id, post_id=next_post['_id'],
                is_gallery=is_gallery, gallery_filters=gallery_filters
            )

            self.stack.db.callback_data.update_one(
                {'chat_id': gallery_message.chat.id, 'message_id': gallery_message.message_id, 'post_id': next_post['_id']},
                {'$set': {'gallery_filters': gallery_filters, 'is_gallery': is_gallery, 'preview': False}},
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
            print(message.text)
            if self.stack.user.state not in [states.ASK_QUESTION, states.ANSWER_QUESTION, states.COMMENT_POST]:
                return

            supported_contents = self.stack.user.post.supported_content_types
            if message.content_type not in supported_contents:
                self.stack.user.send_message(
                    constants.UNSUPPORTED_CONTENT_TYPE_MESSAGE.format(supported_contents=' '.join(supported_contents))
                )
                return

            self.stack.user.post.update(message, replied_to_post_id=self.stack.user.tracker.get('replied_to_post_id'))
            new_preview_message = self.stack.user.post.send_to_one(chat_id=message.chat.id, preview=True)
            self.stack.user.clean_preview(new_preview_message.message_id)

    def send_gallery(self, chat_id, post_id, is_gallery=False, gallery_filters=None):
        """
        Send gallery of posts starting with the post with post_id.

        :param chat_id: Chat id to send gallery to.
        :param post_id: Post id to start gallery from.
        :param is_gallery: If True, send gallery of posts. If False, send single post.
            Next and previous buttions will be added to the message if is_gallery is True.
        """
        post_handler = Post(
            mongodb=self.stack.user.db, stackbot=self.stack,
            post_id=post_id, chat_id=self.stack.user.chat_id,
            is_gallery=is_gallery, gallery_filters=gallery_filters
        )
        message = self.stack.user.send_message(
            text=post_handler.get_text(),
            reply_markup=post_handler.get_keyboard(),
            delete_after=False,
        )

        # if user asks for this gallery again, we delete the old one to keep the history clean.
        self.stack.user.clean_preview(message.message_id)

        # we should store the callback data for the new message
        self.stack.db.callback_data.insert_one({
            'chat_id': chat_id,
            'message_id': message.message_id,
            'post_id': post_id,
            'preview': False,
            'is_gallery': is_gallery,
            'gallery_filtes': gallery_filters,
        })

        return message
