import re

from src import constants
from src.constants import keyboards, post_types, states
from src.handlers.base import BaseHandler
from src.user import User
from src.data_models.base import BasePost
from bson import ObjectId


class CommandHandler(BaseHandler):
    def register(self):
        @self.stackbot.bot.middleware_handler(update_types=['message'])
        def init_message_handler(bot_instance, message):
            """
            Initialize user to use in other message handlers.

            1. Get user object (also registers user if not exists)
            """
            # Getting updated user before message reaches any other handler
            self.stackbot.user = User(
                chat_id=message.chat.id, first_name=message.chat.first_name,
                db=self.db, stackbot=self.stackbot,
            )

        @self.stackbot.bot.message_handler(commands=['start'])
        def start(message):
            """
            This handler is called when user sends /start command.

            1. Send Welcome Message
            2. Insert (if user is new, or update) user in database.
            3. Reset user data (settings, state, track data)
            """
            self.stackbot.user.reset()
            self.stackbot.user.register(message)

            # Parse message text to get what user wants
            match = re.match('\/start (?P<action>\w+)_(?P<post_id>.+)', message.text)
            if not match:
                return

            action = match.group('action')
            post_id = ObjectId(match.group('post_id'))

            # Get the post type
            current_post_type = post_types.ANSWER if action == 'answer' else post_types.COMMENT

            # Update user
            self.stackbot.user.update_state(states.ANSWER_QUESTION if action == 'answer' else states.COMMENT_POST)
            self.stackbot.user.track(replied_to_post_id=post_id)

            # Send the requested post
            self.stackbot.user.post = BasePost(
                db=self.stackbot.user.db, stackbot=self.stackbot,
                post_id=post_id, chat_id=self.stackbot.user.chat_id,
            )
            self.stackbot.user.post.send_to_one(self.stackbot.user.chat_id)

            # Ask user for his action input
            self.stackbot.user.send_message(
                constants.POST_START_MESSAGE.format(
                    first_name=self.stackbot.user.first_name,
                    post_type=current_post_type
                ),
                reply_markup=keyboards.send_post,
            )
