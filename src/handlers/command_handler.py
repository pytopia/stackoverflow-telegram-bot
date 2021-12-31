from src.handlers.base import BaseHandler
from src.user import User


class CommandHandler(BaseHandler):
    def register(self):
        @self.stack.bot.middleware_handler(update_types=['message'])
        def init_message_handler(bot_instance, message):
            """
            Initialize user to use in other message handlers.

            1. Get user object (also registers user if not exists)
            """
            # Getting updated user before message reaches any other handler
            self.user = User(
                chat_id=message.chat.id, first_name=message.chat.first_name,
                mongodb=self.db, stackbot=self.stack,
            )

        @self.stack.bot.message_handler(commands=['start'])
        def start(message):
            """
            This handler is called when user sends /start command.

            1. Send Welcome Message
            2. Insert (if user is new, or update) user in database.
            3. Reset user data (settings, state, track data)
            """
            self.user.reset()
