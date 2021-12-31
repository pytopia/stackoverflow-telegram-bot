import emoji
from src import constants
from src.bot import bot
from src.constants import keyboards, keys, post_status, post_type, states
from src.data_models.post import Post
from src.handlers.base import BaseHandler
from src.user import User


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
            self.stack.user = User(
                chat_id=message.chat.id, first_name=message.chat.first_name,
                mongodb=self.db, stackbot=self.stack,
            )

            # register if not exits already
            self.stack.user.register(message)

            # Demojize text
            if message.content_type == 'text':
                message.text = emoji.demojize(message.text)

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
            User wants to change settings.
            """
            self.stack.user.send_message(self.get_settings_text(), self.get_settings_keyboard())

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
            4. Delete previous post preview.
            """
            if self.stack.user.state not in [states.ASK_QUESTION, states.ANSWER_QUESTION, states.COMMENT_POST]:
                return

            # Not all types of post support all content types. For example comments do not support texts.
            supported_contents = self.stack.user.post.supported_content_types
            if message.content_type not in supported_contents:
                self.stack.user.send_message(
                    constants.UNSUPPORTED_CONTENT_TYPE_MESSAGE.format(supported_contents=' '.join(supported_contents))
                )
                return

            # Update the post content with the new message content
            self.stack.user.post.update(message, replied_to_post_id=self.stack.user.tracker.get('replied_to_post_id'))

            # Send message preview to the user
            new_preview_message = self.stack.user.post.send_to_one(chat_id=message.chat.id, preview=True)

            # Delete previous preview message and set the new one
            self.stack.user.clean_preview(new_preview_message.message_id)

    def send_gallery(self, gallery_filters=None):
        """
        Send gallery of posts starting with the post with post_id.

        1. Get posts from database.
        2. Send posts to the user.
        3. Store callback data for the gallery.
        4. Clean the preview messages as galleries are not meant to stay in bot history.
            We delete the galleries after a period of time to keep the bot history clean.

        :param chat_id: Chat id to send gallery to.
        :param post_id: Post id to start gallery from.
        :param is_gallery: If True, send gallery of posts. If False, send single post.
            Next and previous buttions will be added to the message if is_gallery is True.
        """
        posts = self.db.post.find(gallery_filters).sort('date', -1)
        try:
            next_post_id = next(posts)['_id']
        except StopIteration:
            text = constants.GALLERY_NO_POSTS_MESSAGE.format(post_type=gallery_filters.get('type', 'post'))
            self.stack.user.send_message(text)
            return

        # Send the posts gallery
        num_posts = self.db.post.count_documents(gallery_filters)
        is_gallery = True if num_posts > 1 else False

        self.stack.user.post = Post(
            mongodb=self.stack.user.db, stackbot=self.stack,
            post_id=next_post_id, chat_id=self.stack.user.chat_id,
            is_gallery=is_gallery, gallery_filters=gallery_filters
        )

        # Send the gallery message
        post_text, post_keyboard = self.stack.user.post.get_text_and_keyboard()
        message = self.stack.user.send_message(
            text=post_text,
            reply_markup=post_keyboard,
            delete_after=False,
        )

        # if user asks for this gallery again, we delete the old one to keep the history clean.
        self.stack.user.clean_preview(message.message_id)
        return message
