import emoji
from loguru import logger
from telebot import custom_filters

from src import constants
from src.bot import bot
from src.constants import keyboards, keys, states
from src.db import db
from src.filters import IsAdmin
from src.question import Question
from src.user import User


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

    def run(self):
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
            self.user = User(chat_id=message.chat.id, mongodb=self.db, stackbot=self, message=message)

            if message.content_type == 'text':
                message.text = emoji.demojize(message.text)

        @self.bot.message_handler(commands=['start'])
        def start(message):
            """
            /start command handler.
            """
            self.user.send_message(constants.WELCOME_MESSAGE.format(**vars(self.user)), reply_markup=keyboards.main)
            self.db.users.update_one({'chat.id': message.chat.id}, {'$set': message.json}, upsert=True)
            self.user.reset()

        @self.bot.message_handler(text=[keys.ask_question])
        def ask_question(message):
            """
            Users starts sending question.
            """
            self.user.update_state(states.ask_question)
            self.user.send_message(constants.HOW_TO_ASK_QUESTION_GUIDE, reply_markup=keyboards.ask_question)
            self.user.send_message(constants.ASK_QUESTION_START_MESSAGE.format(**vars(self.user)))

        @self.bot.message_handler(text=[keys.cancel])
        def cancel(message):
            """
            User cancels question.
            """
            self.user.reset()
            self.user.send_message(constants.CANCEL_MESSAGE, reply_markup=keyboards.main)

        @self.bot.message_handler(text=[keys.send_question])
        def send_question(message):
            """
            User sends question.

            If question is empty, user can continue.
            """
            save_status = self.user.persist_question()
            if not save_status:
                return

            self.user.send_message(constants.QUESTION_SAVE_SUCCESS_MESSAGE, reply_markup=keyboards.main)
            self.user.send_question_to_all()
            self.user.reset()

        # Handles all other messages with the supported content_types
        @bot.message_handler(content_types=constants.SUPPORTED_CONTENT_TYPES)
        def echo(message):
            """
            Respond to user according to the current user state.
            """
            if not self.user.state == states.ask_question:
                return
            from pprint import pprint
            pprint(message.json)

            self.user.update_current_question(message)
            question_text, question_keyboard = self.user.preview_current_question()
            self.user.send_message(question_text, reply_markup=question_keyboard)

        @bot.callback_query_handler(func=lambda call: True)
        def test_callback(call): # <- passes a CallbackQuery type object to your function
            from pprint import pprint
            self.db.questions.find_one({'': call.data})
            pprint(call.data)
            self.bot.answer_callback_query(call.id, text=call.data)


    def send_message(self, chat_id, text, reply_markup=None, emojize=True):
        """
        Send message to telegram bot having a chat_id and text_content.
        """
        text = emoji.emojize(text) if emojize else text
        self.bot.send_message(chat_id, text, reply_markup=reply_markup)


if __name__ == '__main__':
    logger.info('Bot started...')
    stackbot = StackBot(telebot=bot, mongodb=db)
    stackbot.run()
