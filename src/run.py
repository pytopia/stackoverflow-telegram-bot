import emoji
from loguru import logger
from telebot import custom_filters

from src import constants
from src.bot import bot
from src.constants import inline_keys, keyboards, keys, post_status, states
from src.db import db
from src.filters import IsAdmin
from src.question import Question
from src.user import User
from src.utils.keyboard import create_keyboard


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

        # question object to handle send/recieve questions
        self.question = Question(mongodb=self.db, stackbot=self, post_type='question')

        # register handlers
        self.handlers()

    def run(self):
        # run bot with polling
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

            # Demojize text
            if message.content_type == 'text':
                message.text = emoji.demojize(message.text)

        @self.bot.middleware_handler(update_types=['callback_query'])
        def init_callback_handler(bot_instance, call):
            """
            Initialize user to use in other handlers.
            """
            # Getting updated user before message reaches any other handler
            self.user = User(chat_id=call.message.chat.id, mongodb=self.db, stackbot=self, message=call.message)

            # Getting updated user before message reaches any other handler
            call.data = emoji.demojize(call.data)

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
            if not self.user.state == states.MAIN:
                return

            self.user.update_state(states.ASK_QUESTION)
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
            if not self.user.state == states.ASK_QUESTION:
                return

            # Check if question is empty
            question = self.db.questions.find_one({'chat.id': message.chat.id, 'status': post_status.PREP})
            if not question:
                self.user.send_message(constants.EMPTY_QUESTION_MESSAGE)
                return

            # Send question to all users
            self.question.save(question['_id'])
            self.user.send_message(constants.QUESTION_SAVE_SUCCESS_MESSAGE, reply_markup=keyboards.main)
            self.question.send_to_all(question['_id'])

            # Reset user state and data
            self.user.reset()

        # Handles all other messages with the supported content_types
        @bot.message_handler(content_types=constants.SUPPORTED_CONTENT_TYPES)
        def echo(message):
            """
            Respond to user according to the current user state.
            """
            self.user.send_message(f'State: <strong>{self.user.state}</strong>')
            if self.user.state == states.ASK_QUESTION:
                question_id = self.question.update(message)
                self.question.send_to_one(post_id=question_id, chat_id=message.chat.id, preview=True)

            elif self.user.state == states.ANSWER_QUESTION:
                answer_id = self.answer.update(message)

        @bot.callback_query_handler(func=lambda call: call.data == inline_keys.actions)
        def actions_callback(call):
            """Actions >> inline key callback.

            Questions/Answers actions include follow, unfollow, answer, delete, etc.
            """
            self.bot.answer_callback_query(call.id, text=inline_keys.actions)

            # actions keyboard
            self.bot.edit_message_reply_markup(
                call.message.chat.id, call.message.message_id,
                reply_markup=create_keyboard(
                    inline_keys.back, inline_keys.answer, inline_keys.follow, inline_keys.unfollow,
                    is_inline=True
                )
            )

        @bot.callback_query_handler(func=lambda call: call.data == inline_keys.answer)
        def answer_callback(call):
            """
            Answer inline key callback.
            """
            self.bot.answer_callback_query(call.id, text=emoji.emojize(inline_keys.answer))
            self.user.update_state(states.ANSWER_QUESTION)
            self.user.send_message(
                constants.ANSWER_QUESTION_START_MESSAGE.format(**vars(self.user)),
                reply_markup=keyboards.answer_question
            )

        @bot.callback_query_handler(func=lambda call: call.data == inline_keys.back)
        def back_callback(call):
            """
            Back inline key callback.
            """
            self.bot.answer_callback_query(call.id, text=inline_keys.back)

            # main menu keyboard
            question_id = self.get_call_info(call)['question_id']
            self.bot.edit_message_reply_markup(
                call.message.chat.id, call.message.message_id,
                reply_markup=self.question.get_post_keyboard(post_id=question_id)
            )

        @bot.callback_query_handler(func=lambda call: call.data == inline_keys.like)
        def like_callback(call):
            self.bot.answer_callback_query(call.id, text=emoji.emojize(inline_keys.like))

            # add user chat_id to likes
            question_id = self.get_call_info(call)['post_id']
            self.question.like(call.message.chat.id, question_id)
            self.bot.edit_message_reply_markup(
                call.message.chat.id, call.message.message_id,
                reply_markup=self.question.get_post_keyboard(post_id=question_id)
            )

        @bot.callback_query_handler(func=lambda call: True)
        def send_file(call):
            """
            Send file callback. Callback data is file_unique_id. We use this to get file from telegram database.
            """
            print(call.data)
            self.bot.answer_callback_query(call.id, text=f'Sending file: {call.data}...')
            self.send_file(call.message.chat.id, call.data, message_id=call.message.message_id)

    def send_message(self, chat_id, text, reply_markup=None, emojize=True):
        """
        Send message to telegram bot having a chat_id and text_content.
        """
        text = emoji.emojize(text) if emojize else text
        message = self.bot.send_message(chat_id, text, reply_markup=reply_markup)

        return message

    def send_file(self, chat_id, file_unique_id, message_id=None):
        """
        Send file to telegram bot having a chat_id and file_id.
        """
        file_id, content_type, mime_type = self.file_unique_id_to_content(file_unique_id)

        # Send file to user with the appropriate send_file method according to the content_type
        send_method = getattr(self.bot, f'send_{content_type}')
        send_method(
            chat_id, file_id,
            reply_to_message_id=message_id,
            caption=f"<code>{mime_type or ''}</code>",
        )

    def file_unique_id_to_content(self, file_unique_id):
        collections = ['questions', 'answers']
        for collection in collections:
            collection = getattr(self.db, collection)
            query_result = collection.find_one({'content.file_unique_id': file_unique_id}, {'content.$': 1})
            content = query_result['content'][0]

            return content['file_id'], content['content_type'], content.get('mime_type')

    def get_call_info(self, call):
        return self.db.callback_data.find_one({'chat_id': call.message.chat.id, 'message_id': call.message.message_id})

if __name__ == '__main__':
    logger.info('Bot started...')
    stackbot = StackBot(telebot=bot, mongodb=db)
    stackbot.run()
