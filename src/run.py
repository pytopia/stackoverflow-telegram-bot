import emoji
from loguru import logger
from telebot import custom_filters

from src import constants
from src.bot import bot
from src.constants import inline_keys, keyboards, keys, states
from src.db import db
from src.filters import IsAdmin
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
        # run bot with polling
        logger.info('Bot is running...')
        self.bot.infinity_polling()

    def handlers(self):
        @self.bot.message_handler(commands=['start'])
        def start(message):
            """
            /start command handler.
            """
            self.user.send_message(constants.WELCOME_MESSAGE.format(**vars(self.user)), reply_markup=keyboards.main)
            self.db.users.update_one({'chat.id': message.chat.id}, {'$set': message.json}, upsert=True)
            self.user.reset()

        @self.bot.middleware_handler(update_types=['message'])
        def init_handler(bot_instance, message):
            """
            Initialize user to use in other handlers.
            """
            # Getting updated user before message reaches any other handler
            self.user = User(
                chat_id=message.chat.id, mongodb=self.db,
                stackbot=self, first_name=message.chat.first_name,
            )
            if not self.user.exists():
                self.user.reset()
                return

            # Demojize text
            if message.content_type == 'text':
                message.text = emoji.demojize(message.text)

        @self.bot.middleware_handler(update_types=['callback_query'])
        def init_callback_handler(bot_instance, call):
            """
            Initialize user to use in other handlers.
            """
            # Getting updated user before message reaches any other handler
            self.user = User(
                chat_id=call.message.chat.id, mongodb=self.db,
                stackbot=self, first_name=call.message.chat.first_name,
                post_type=self.get_call_info(call)['post_type']
            )

            # Demojize callback data
            call.data = emoji.demojize(call.data)

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
            User cancels sending a post.
            """
            self.user.reset()
            self.user.send_message(constants.CANCEL_MESSAGE, reply_markup=keyboards.main)

        @self.bot.message_handler(text=[keys.send_question, keys.send_answer])
        def send_post(message):
            """
            User sends a post.
            """
            self.user.post.submit()
            self.user.send_message(
                text=constants.POST_OPEN_SUCCESS_MESSAGE.format(
                    post_type=self.user.post.post_type.title(),
                ),
                reply_markup=keyboards.main
            )

            # Reset user state and data
            self.user.reset()

        # Handles all other messages with the supported content_types
        @bot.message_handler(content_types=constants.SUPPORTED_CONTENT_TYPES)
        def echo(message):
            """
            Respond to user according to the current user state.
            """
            if self.user.state not in [states.ASK_QUESTION, states.ANSWER_QUESTION]:
                return

            post_metadata = dict()
            if self.user.state == states.ANSWER_QUESTION:
                post_metadata.update({'question_id': self.user.tracker['post_id']})

            post_id = self.user.post.update(message, post_metadata)
            self.user.post.send_to_one(post_id=post_id, chat_id=message.chat.id, preview=True)

        @bot.callback_query_handler(func=lambda call: call.data == inline_keys.actions)
        def actions_callback(call):
            """Actions >> inline key callback.

            Questions/Answers actions include follow, unfollow, answer, delete, etc.
            """
            self.bot.answer_callback_query(call.id, text=inline_keys.actions)

            # actions keyboard'
            post_id = self.get_call_info(call)['post_id']
            reply_markup = self.user.post.get_actions_keyboard(post_id, call.message.chat.id)

            self.edit_message(call.message.chat.id, call.message.message_id, reply_markup=reply_markup)

        @bot.callback_query_handler(func=lambda call: call.data == inline_keys.answer)
        def answer_callback(call):
            """
            Answer inline key callback.
            """
            self.bot.answer_callback_query(call.id, text=emoji.emojize(inline_keys.answer))

            # we store empty answer in db to track the question_id we are answering
            question_id = self.get_call_info(call)['post_id']
            self.user.track(action_on='question', post_id=question_id)

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
            post_id = self.get_call_info(call)['post_id']
            self.edit_message(
                call.message.chat.id, call.message.message_id,
                reply_markup=self.user.post.get_keyboard(post_id=post_id)
            )

        @bot.callback_query_handler(func=lambda call: call.data == inline_keys.like)
        def like_callback(call):
            self.bot.answer_callback_query(call.id, text=emoji.emojize(inline_keys.like))

            # add user chat_id to likes
            question_id = self.get_call_info(call)['post_id']
            self.user.post.like(question_id)

            # update main menu keyboard
            self.edit_message(
                call.message.chat.id, call.message.message_id,
                reply_markup=self.user.post.get_keyboard(post_id=question_id)
            )

        @bot.callback_query_handler(func=lambda call: True)
        def send_file(call):
            """
            Send file callback. Callback data is file_unique_id. We use this to get file from telegram database.
            """
            self.bot.answer_callback_query(call.id, text=f'Sending file: {call.data}...')
            self.send_file(call.message.chat.id, call.data, message_id=call.message.message_id)

    def send_message(self, chat_id, text, reply_markup=None, emojize=True):
        """
        Send message to telegram bot having a chat_id and text_content.
        """
        text = emoji.emojize(text) if emojize else text
        message = self.bot.send_message(chat_id, text, reply_markup=reply_markup)

        return message

    def edit_message(self, chat_id, message_id, text=None, reply_markup=None):
        """
        Edit telegram message text and/or reply_markup.
        """
        # if message text or reply_markup is the same as before, telegram raises an invalid request error
        # so we are doing try/catch to avoid this.
        try:
            if reply_markup:
                self.bot.edit_message_reply_markup(chat_id, message_id, reply_markup=reply_markup)
            if text:
                self.bot.edit_message_text(chat_id, message_id, text=text)
        except Exception as e:
            logger.warning(e)

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
