import bson
import emoji
from loguru import logger
from src import constants
from src.bot import bot
from src.constants import keyboards, keys, post_status, post_types, states
from src.data_models.base import BasePost
from src.handlers.base import BaseHandler
from src.user import User


class MessageHandler(BaseHandler):
    def register(self):
        @self.stackbot.bot.middleware_handler(update_types=['message'])
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
            self.stackbot.user = User(
                chat_id=message.chat.id, first_name=message.chat.first_name,
                db=self.db, stackbot=self.stackbot,
            )

            # register if not exits already
            if not self.stackbot.user.is_registered:
                self.stackbot.user.register(message)

            # Demojize text
            if message.content_type == 'text':
                message.text = emoji.demojize(message.text)

            self.stackbot.queue_message_deletion(message.chat.id, message.message_id, constants.DELETE_USER_MESSAGES_AFTER_TIME)

        @self.stackbot.bot.message_handler(text=[keys.ask_question])
        def ask_question(message):
            """
            Users starts sending question.

            1. Update state.
            2. Send how to ask a question guide.
            3. Send start typing message.
            """
            if not self.stackbot.user.state == states.MAIN:
                return

            self.stackbot.user.update_state(states.ASK_QUESTION)
            self.stackbot.user.send_message(constants.HOW_TO_ASK_QUESTION_GUIDE, reply_markup=keyboards.send_post)
            self.stackbot.user.send_message(constants.POST_START_MESSAGE.format(
                first_name=self.stackbot.user.first_name, post_type='question'
            ))

        @self.stackbot.bot.message_handler(text=[keys.cancel, keys.back])
        def cancel_back(message):
            """
            User cancels sending a post.

            1. Reset user state and data.
            2. Send cancel message.
            3. Delete previous bot messages.
            """
            self.stackbot.user.clean_preview()
            self.stackbot.user.send_message(constants.BACK_TO_HOME_MESSAGE, reply_markup=keyboards.main)
            self.stackbot.user.reset()

        @self.stackbot.bot.message_handler(text=[keys.send_post])
        def send_post(message):
            """
            User sends a post.

            1. Submit post to database.
            2. Check if post is not empty.
            3. Send post to the relevant audience.
            4. Reset user state and data.
            5. Delete previous bot messages.
            """
            post_id = self.stackbot.user.post.submit()
            if not post_id:
                # Either post is empty or too short
                return

            self.stackbot.user.post.post_id = post_id
            self.stackbot.user.post.send()
            self.stackbot.user.send_message(
                text=constants.POST_OPEN_SUCCESS_MESSAGE.format(
                    post_type=self.stackbot.user.post.post_type.title(),
                ),
                reply_markup=keyboards.main
            )

            # Reset user state and data
            self.stackbot.user.clean_preview()
            self.stackbot.user.reset()

        @self.stackbot.bot.message_handler(text=[keys.settings])
        def settings(message):
            """
            User wants to change settings.
            """
            self.stackbot.user.send_message(self.get_settings_text(), self.get_settings_keyboard())

        @self.stackbot.bot.message_handler(text=[keys.search_questions])
        def search_questions(message):
            """
            User asks for all questions to search through.
            """
            gallery_filters = {'type': post_types.QUESTION, 'status': post_status.OPEN}
            self.send_gallery(gallery_filters=gallery_filters)

        @self.stackbot.bot.message_handler(text=[
            keys.my_questions, keys.my_answers, keys.my_comments, keys.my_bookmarks
        ])
        def send_user_data(message):
            """
            User asks for all questions to search through.
            """
            if message.text == keys.my_bookmarks:
                # Bookmarks are stored in user collection not each post
                # This makes it faster to fetch all bookmarks
                post_ids = self.db.users.find_one({'chat.id': message.chat.id}).get('bookmarks', [])
                gallery_filters = {'_id': {'$in': post_ids}}
            else:
                if message.text == keys.my_questions:
                    filter_type = post_types.QUESTION
                elif message.text == keys.my_answers:
                    filter_type = post_types.ANSWER
                elif message.text == keys.my_comments:
                    filter_type = post_types.COMMENT
                gallery_filters = {'type': filter_type, 'chat.id': message.chat.id}

            self.send_gallery(gallery_filters=gallery_filters)

        @self.stackbot.bot.message_handler(text=[keys.my_data])
        def my_data(message):
            """
            User asks for all his data (Questions, Answers, Comments, etc.)
            """
            # we should change the post_id for the buttons
            self.stackbot.user.send_message(constants.MY_DATA_MESSAGE, keyboards.my_data)

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
            print(message.text)
            if self.stackbot.user.state in states.MAIN:
                post_id = message.text

                try:
                    self.stackbot.user.post = BasePost(
                        db=self.stackbot.user.db, stackbot=self.stackbot,
                        post_id=post_id, chat_id=self.stackbot.user.chat_id,
                    )
                    self.stackbot.user.post.send_to_one(message.chat.id)
                except bson.errors.InvalidId:
                    logger.warning('Invalid post id: {post_id}')
                return

            elif self.stackbot.user.state in [states.ASK_QUESTION, states.ANSWER_QUESTION, states.COMMENT_POST]:
                # Not all types of post support all content types. For example comments do not support texts.
                supported_contents = self.stackbot.user.post.supported_content_types
                if message.content_type not in supported_contents:
                    self.stackbot.user.send_message(
                        constants.UNSUPPORTED_CONTENT_TYPE_MESSAGE.format(supported_contents=' '.join(supported_contents))
                    )
                    return

                # Update the post content with the new message content
                self.stackbot.user.post.update(message, replied_to_post_id=self.stackbot.user.tracker.get('replied_to_post_id'))

                # Send message preview to the user
                new_preview_message = self.stackbot.user.post.send_to_one(chat_id=message.chat.id, preview=True)

                # Delete previous preview message and set the new one
                self.stackbot.user.clean_preview(new_preview_message.message_id)
                return

    def send_gallery(self, gallery_filters=None, order_by='date'):
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
        posts = self.db.post.find(gallery_filters)
        if order_by:
            posts = posts.sort(order_by, -1)

        try:
            next_post_id = next(posts)['_id']
        except StopIteration:
            text = constants.GALLERY_NO_POSTS_MESSAGE.format(post_type=gallery_filters.get('type', 'post'))
            self.stackbot.user.send_message(text)
            return

        # Send the posts gallery
        num_posts = self.db.post.count_documents(gallery_filters)
        is_gallery = True if num_posts > 1 else False

        self.stackbot.user.post = BasePost(
            db=self.stackbot.user.db, stackbot=self.stackbot,
            post_id=next_post_id, chat_id=self.stackbot.user.chat_id,
            is_gallery=is_gallery, gallery_filters=gallery_filters
        )
        message = self.stackbot.user.post.send_to_one(self.stackbot.user.chat_id)

        # if user asks for this gallery again, we delete the old one to keep the history clean.
        self.stackbot.user.clean_preview(message.message_id)
        return message
