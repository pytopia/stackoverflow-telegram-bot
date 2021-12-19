import emoji
from loguru import logger
from telebot import custom_filters

from src.bot import bot
from src.constants import keyboards, keys, states
from src.data import DATA_DIR
from src.db import db
from src.filters import IsAdmin
from src.user import User
from src.utils.io import read_file


class StackBot:
    """
    Template for telegram bot.
    """
    def __init__(self, telebot, mongodb):
        self.bot = telebot
        self.db = mongodb

        # add custom filters
        self.bot.add_custom_filter(IsAdmin())
        self.bot.add_custom_filter(custom_filters.TextMatchFilter())
        self.bot.add_custom_filter(custom_filters.TextStartsFilter())

        # register handlers
        self.handlers()

        # run bot
        logger.info('Bot is running...')
        self.bot.infinity_polling()

    def handlers(self):
        @self.bot.middleware_handler(update_types=['message'])
        def init_handler(bot_instance, message):
            """
            Initialize user to use in other handlers.
            """
            # Getting updated user before message reaches any other handler
            self.user = User(
                chat_id=message.chat.id, mongodb=self.db,
                stackbot=self, message=message,
            )
            message.text = emoji.demojize(message.text)

        @self.bot.message_handler(commands=['start'])
        def start(message):
            """
            /start command handler.
            """
            self.user.send_message(
                f"Hey <strong>{message.chat.first_name}</strong>!",
                reply_markup=keyboards.main
            )

            self.db.users.update_one(
                {'chat.id': message.chat.id},
                {'$set': message.json},
                upsert=True
            )
            self.user.reset()

        @self.bot.message_handler(text=[keys.ask_question])
        def ask_question(message):
            """
            Users starts sending question.
            """
            self.update_state(message.chat.id, states.ask_question)
            guide_text = read_file(DATA_DIR / 'guide.html')
            self.user.send_message(guide_text, reply_markup=keyboards.ask_question)

        @self.bot.message_handler(text=[keys.cancel])
        def cancel(message):
            """
            User cancels question.
            """
            self.user.reset()
            self.user.send_message(':cross_mark: Canceled.', reply_markup=keyboards.main)

        @self.bot.message_handler(text=[keys.send_question])
        def send_question(message):
            """
            User sends question.

            If question is empty, user can continue.
            """
            save_status = self.user.save_question()
            if not save_status:
                return

            self.user.send_message(
                ':check_mark_button: Question saved successfully.',
                reply_markup=keyboards.main
            )
            self.user.send_question_to_all()
            self.user.reset()

        @self.bot.message_handler(func=lambda ـ: True)
        def echo(message):
            """
            Respond to user according to the current user state.
            """
            if self.user.state == states.ask_question:
                self.db.users.update_one(
                    {'chat.id': message.chat.id},
                    {'$push': {'current_question': message.text}},
                )
                self.send_message(
                    message.chat.id,
                    self.user.current_question,
                )
            print(message.text)

    def send_message(self, chat_id, text, reply_markup=None, emojize=True):
        """
        Send message to telegram bot having a chat_id and text_content.
        """
        if emojize:
            text = emoji.emojize(text)

        self.bot.send_message(chat_id, text, reply_markup=reply_markup)


if __name__ == '__main__':
    logger.info('Bot started')
    nashenas_bot = StackBot(telebot=bot, mongodb=db)
    nashenas_bot.run()
