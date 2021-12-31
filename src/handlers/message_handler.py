import emoji
from src import constants
from src.bot import bot
from src.constants import (DELETE_USER_MESSAGES_AFTER_TIME, keyboards, keys,
                           post_status, post_type, states)
from src.data_models.post import Post
from src.handlers.base import BaseHandler
from src.user import User
from loguru import logger


class MessageHandler(BaseHandler):
    def register(self):
        @self.stack.bot.middleware_handler(update_types=['message'])
        def init_message_handler(bot_instance, message):
            """
            Initialize user to use in other message handlers.

            1. Get user object (also registers user if not exists)
            3. Demojize message text.
            4. Send user message for auto deletion.
                All user messages gets deleted from bot after a period of time to keep the bot history clean.
                This is managed a cron job that deletes old messages periodically.
            """
            # Getting updated user before message reaches any other handler
            self.user = User(
                chat_id=message.chat.id, first_name=message.chat.first_name,
                mongodb=self.db, stackbot=self.stack,
            )

            # register if not exits already
            self.user.register(message)

            # Demojize text
            if message.content_type == 'text':
                message.text = emoji.demojize(message.text)

            # Auto delete user message to keep the bot clean
            self.stack.queue_message_deletion(message.chat.id, message.message_id, DELETE_USER_MESSAGES_AFTER_TIME)

        @self.stack.bot.message_handler(text=[keys.ask_question])
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

        @self.stack.bot.message_handler(text=[keys.cancel])
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

        @self.stack.bot.message_handler(text=[keys.settings])
        def settings(message):
            """
            User wants to change settings.
            """
            self.user.send_message(self.get_settings_text(), self.get_settings_keyboard())

        @self.stack.bot.message_handler(text=[keys.search_questions])
        def search_questions(message):
            """
            User asks for all questions to search through.
            """
            # we should change the post_id for the buttons
            gallery_filters = {'type': post_type.QUESTION, 'status': post_status.OPEN}
            self.send_gallery(gallery_filters=gallery_filters)

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

    def send_gallery(self, gallery_filters=None):
        """
        Send gallery of posts starting with the post with post_id.

        :param chat_id: Chat id to send gallery to.
        :param post_id: Post id to start gallery from.
        :param is_gallery: If True, send gallery of posts. If False, send single post.
            Next and previous buttions will be added to the message if is_gallery is True.
        """
        posts = self.db.post.find(gallery_filters).sort('date', -1)
        num_posts = self.db.post.count_documents(gallery_filters)
        try:
            next_post_id = next(posts)['_id']
        except StopIteration:
            text = constants.GALLERY_NO_POSTS_MESSAGE.format(post_type=gallery_filters.get('type', 'post'))
            self.user.send_message(text)
            return

        is_gallery = True if num_posts > 1 else False
        post_handler = Post(
            mongodb=self.user.db, stackbot=self.stack,
            post_id=next_post_id, chat_id=self.user.chat_id,
            is_gallery=is_gallery, gallery_filters=gallery_filters
        )
        message = self.user.send_message(
            text=post_handler.get_text(),
            reply_markup=post_handler.get_keyboard(),
            delete_after=False,
        )

        # if user asks for this gallery again, we delete the old one to keep the history clean.
        self.user.clean_preview(message.message_id)

        # we should store the callback data for the new message
        output = self.db.callback_data.insert_one({
            'chat_id': self.user.chat_id,
            'message_id': message.message_id,
            'post_id': next_post_id,
            'preview': False,
            'is_gallery': is_gallery,
            'gallery_filters': gallery_filters,
        })
        logger.info(f'INSERT: Callback data for message {message.message_id}: {next_post_id}')
        return message
