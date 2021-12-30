import re
import time

import emoji
from loguru import logger
from telebot import custom_filters

from src import constants
from src.bot import bot
from src.constants import (DELETE_BOT_MESSAGES_AFTER_TIME,
                           DELETE_USER_MESSAGES_AFTER_TIME, inline_keys,
                           keyboards, keys, post_type, states)
from src.data_models.post import Post
from src.db import db
from src.filters import IsAdmin
from src.user import User
from src.utils.keyboard import create_keyboard


class StackBot:
    """
    Stackoverflow Telegram Bot.

    Using the Telegram Bot API, users can interact with each other to ask questions,
    comment, and answer.
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
            This handler is called when user sends /start command.

            1. Send Welcome Message
            2. Insert (if user is new, or update) user in database.
            3. Reset user data (settings, state, track data)
            """
            self.user.register(message)

        @self.bot.middleware_handler(update_types=['message'])
        def init_message_handler(bot_instance, message):
            """
            Initialize user to use in other message handlers.

            1. Get user object.
            2. Demojize message text.
            """
            # Getting updated user before message reaches any other handler
            self.user = User(
                chat_id=message.chat.id, first_name=message.chat.first_name,
                mongodb=self.db, stackbot=self,
            )

            # Register user if not exists
            if not self.user.exists():
                self.user.register(message)

            # Demojize text
            if message.content_type == 'text':
                message.text = emoji.demojize(message.text)

            # Auto delete user message to keep the bot clean
            self.queue_delete_message(message.chat.id, message.message_id, DELETE_USER_MESSAGES_AFTER_TIME)

        @self.bot.middleware_handler(update_types=['callback_query'])
        def init_callback_handler(bot_instance, call):
            """
            Initialize user to use in other callback handlers.

            1. Get user object.
            2. Demojize call data and call message text.
            """
            # Every message sent with inline keyboard is stored in database with callback_data and
            # post_type (question, answer, comment, ...). When user clicks on an inline keyboard button,
            # we get the post type to know what kind of post we are dealing with.
            call_info = self.get_call_info(call)
            post_id = call_info.get('post_id')
            self.user = User(
                chat_id=call.message.chat.id, first_name=call.message.chat.first_name,
                mongodb=self.db, stackbot=self,
                post_id=post_id
            )

            # register user if not exists
            if not self.user.exists():
                self.user.register(call.message)

            self.user.post.is_gallery = call_info.get('is_gallery', False)

            # Demojize text
            call.data = emoji.demojize(call.data)
            call.message.text = emoji.demojize(call.message.text)

        @self.bot.message_handler(text=[keys.ask_question])
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

        @self.bot.message_handler(text=[keys.cancel])
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

        @self.bot.message_handler(text=[keys.send_post])
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

        @self.bot.message_handler(text=[keys.settings])
        def settings(message):
            """
            User cancels sending a post.

            1. Send Settings Message.
            """
            if self.user.state != states.MAIN:
                return

            self.user.send_message(text=self.get_settings_text(), reply_markup=self.get_settings_keyboard())

        @self.bot.message_handler(text=[keys.search_questions])
        def search_questions(message):
            """
            User cancels sending a post.

            1. Send Settings Message.
            """
            if self.user.state != states.MAIN:
                return

            # self.user.update_state(states.SEARCH_QUESTIONS)

            posts = self.db.post.find({'type': post_type.QUESTION}).sort('date', -1)
            num_posts = self.db.post.count_documents({'type': post_type.QUESTION})
            next_post = next(posts)

            is_gallery = True if num_posts > 1 else False

            self.send_gallery(chat_id=message.chat.id, post_id=next_post['_id'], is_gallery=is_gallery)

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

        @bot.callback_query_handler(func=lambda call: call.data == inline_keys.actions)
        def actions_callback(call):
            """Actions >> inline key callback.
            Post actions include follow/unfollow, answer, comment, open/close, edit, ...

            1. Create actions keyboard according to the current post type.
            2. Get post text content.
            3. Edit message with post text and actions keyboard.
            """
            self.answer_callback_query(call.id, text=call.data)

            # actions keyboard (also update text)
            reply_markup = self.user.post.get_actions_keyboard()

            # TODO: If in future, we update the posts in a queue structure, we can remove this
            text = self.user.post.get_text()

            self.edit_message(call.message.chat.id, call.message.message_id, text=text, reply_markup=reply_markup)

        @bot.callback_query_handler(func=lambda call: call.data in [inline_keys.answer, inline_keys.comment])
        def answer_comment_callback(call):
            """
            Answer/Comment inline key callback.

            1. Update user state.
            2. Store replied to post_id in user tracker for storing the answer/comment when user is done.
                When user sends a reply to a post, there will be replied_to_post_id key stored in the user tracker
                to store the post_id of the post that the user replied to in the answer/comment or any other reply type.
            3. Send start typing message.
            """
            self.answer_callback_query(call.id, text=call.data)

            self.user.update_state(states.ANSWER_QUESTION if call.data == inline_keys.answer else states.COMMENT_POST)
            self.user.track(replied_to_post_id=self.user.post_id)

            current_post_type = post_type.COMMENT if call.data == inline_keys.comment else post_type.ANSWER
            self.user.send_message(
                constants.POST_START_MESSAGE.format(
                    first_name=self.user.first_name,
                    post_type=current_post_type
                ),
                reply_markup=keyboards.send_post,
            )

        @bot.callback_query_handler(func=lambda call: call.data == inline_keys.back)
        def back_callback(call):
            """
            Back inline key callback.

            1. Check if back is called on a post or on settings.
                - For a post: Edit message with post keyboard.
                - For settings: Edit message with settings keyboard.
            """
            self.answer_callback_query(call.id, text=call.data)

            # main menu keyboard
            if self.user.post_id is not None:
                # back is called on a post (question, answer or comment)
                self.edit_message(
                    call.message.chat.id, call.message.message_id,
                    reply_markup=self.user.post.get_keyboard()
                )
            else:
                # back is called in settings
                self.edit_message(
                    call.message.chat.id, call.message.message_id,
                    reply_markup=self.get_settings_keyboard()
                )

        @bot.callback_query_handler(
            func=lambda call: call.data in [inline_keys.like, inline_keys.follow, inline_keys.unfollow]
        )
        def toggle_callback(call):
            """
            Toggle callback is used for actions that toggle between pull and push data, such as like, follow, ...

            1. Process callback according to the toggle type.
                - Like: Push/Pull user chat_id from post likes.
                - Follow: Push/Pull user chat_id from post followers.
                - ...
            2. Edit message with new keyboard that toggles based on pull/push.
            """
            self.answer_callback_query(call.id, text=call.data)

            if call.data == inline_keys.like:
                self.user.post.like()
                keyboard = self.user.post.get_keyboard()

            elif call.data in [inline_keys.follow, inline_keys.unfollow]:
                self.user.post.follow()
                keyboard = self.user.post.get_actions_keyboard()

            # update main menu keyboard
            self.edit_message(
                call.message.chat.id, call.message.message_id,
                reply_markup=keyboard
            )

        @bot.callback_query_handler(
            func=lambda call: call.data in [inline_keys.open, inline_keys.close]
        )
        def open_close_post_callback(call):
            """
            Open/Close post.
            Open means that the post is open for new answers, comments, ...

            1. Open/Close post with post_id.
            2. Edit message with new keyboard and text
                - New post text reflects the new open/close status.
            """
            self.answer_callback_query(call.id, text=call.data)

            self.user.post.open_close()

            # update main menu keyboard
            self.edit_message(
                call.message.chat.id, call.message.message_id,
                text=self.user.post.get_text(),
                reply_markup=self.user.post.get_actions_keyboard()
            )

        @bot.callback_query_handler(func=lambda call: call.data == inline_keys.change_identity)
        def change_identity_callback(call):
            """
            Change identity inline key callback.

            1. Update settings with change identity keys.
                - User can choose identity between:
                    - Anonymous
                    - Username
                    - First name
            """
            self.answer_callback_query(call.id, text=call.data)

            keyboard = create_keyboard(
                inline_keys.ananymous, inline_keys.first_name, inline_keys.username,
                is_inline=True
            )
            self.edit_message(call.message.chat.id, call.message.message_id, reply_markup=keyboard)

        @bot.callback_query_handler(
            func=lambda call: call.data in [inline_keys.ananymous, inline_keys.first_name, inline_keys.username]
        )
        def set_identity_callback(call):
            """
            Set new user identity.

            1. Update settings with new identity.
            2. Edit message with new settings text and main keyboard.
            """
            self.answer_callback_query(call.id, text=call.data)

            self.user.update_settings(identity_type=call.data)
            self.edit_message(
                call.message.chat.id, call.message.message_id,
                text=self.get_settings_text(), reply_markup=self.get_settings_keyboard()
            )

        @bot.callback_query_handler(func=lambda call: call.data == inline_keys.original_post)
        def original_post(call):
            """
            Original post inline key callback.

            Get the original post from a reply.

            1. Get the current post.
            2. Get the original post from replied_to_post_id.
            3. Edit message with original post keyboard and text.
            4. Update callback data with original post_id.
            """
            self.answer_callback_query(call.id, text=call.data)

            post = self.user.post.as_dict()
            original_post_id = self.db.post.find_one({'_id': post['replied_to_post_id']})['_id']

            post_handler = Post(
                mongodb=self.user.db, stackbot=self.user.stackbot,
                post_id=original_post_id, chat_id=self.user.chat_id,
            )
            self.edit_message(
                call.message.chat.id, call.message.message_id,
                text=post_handler.get_text(),
                reply_markup=post_handler.get_keyboard()
            )

            # we should change the post_id for the buttons
            self.db.callback_data.update_one(
                {'chat_id': call.message.chat.id, 'message_id': call.message.message_id},
                {'$set': {'post_id': original_post_id, 'preview': False, 'is_gallery': False}},
            )

        @bot.callback_query_handler(
            func=lambda call: call.data in [inline_keys.show_comments, inline_keys.show_answers]
        )
        def show_posts(call):
            """
            """
            self.answer_callback_query(call.id, text=call.data)

            post = self.user.post.as_dict()
            gallery_post_type = post_type.ANSWER if call.data == inline_keys.show_answers else post_type.COMMENT
            posts = self.db.post.find({'replied_to_post_id': post['_id'], 'type': gallery_post_type}).sort('date', -1)
            num_posts = self.db.post.count_documents({'replied_to_post_id': post['_id'], 'type': gallery_post_type})
            next_post = next(posts)

            is_gallery = True if num_posts > 1 else False
            self.edit_gallery(call, next_post['_id'], is_gallery)

        @bot.callback_query_handler(func=lambda call: call.data in [inline_keys.next_post, inline_keys.prev_post])
        def next_prev_callback(call):
            self.answer_callback_query(call.id, text=call.data)

            post = self.user.post.as_dict()
            operator = '$gt' if call.data == inline_keys.next_post else '$lt'
            asc_desc = 1 if call.data == inline_keys.next_post else -1
            posts = self.db.post.find(
                {
                    'replied_to_post_id': post.get('replied_to_post_id'),
                    'type': post['type'],
                    'date': {operator: post['date']}
                }
            ).sort('date', asc_desc)

            try:
                next_post = next(posts)
            except StopIteration:
                self.answer_callback_query(call.id, ':red_exclamation_mark: No more posts!')
                return

            is_gallery = True
            self.edit_gallery(call, next_post['_id'], is_gallery)

        @bot.callback_query_handler(func=lambda call: call.data in [inline_keys.first_page, inline_keys.last_page])
        def gallery_first_last_page(call):
            """
            First and last page of a gallery button.
            """
            self.answer_callback_query(call.id, text=':red_exclamation_mark: No more posts!')

        @bot.callback_query_handler(func=lambda call: re.match(r'[a-zA-Z0-9-]+', call.data))
        def send_file(call):
            """
            Send file callback. Callback data is file_unique_id. We use this to get file from telegram database.
            """
            self.answer_callback_query(call.id, text=f'Sending file: {call.data}...')
            self.send_file(call.message.chat.id, call.data, message_id=call.message.message_id)

        @bot.callback_query_handler(func=lambda call: True)
        def not_implemented_callback(call):
            """
            Raises not implemented callback answer for buttons that are not working yet.
            """
            self.answer_callback_query(call.id, text=f':cross_mark: {call.data} not implemented.')

    def send_gallery(self, chat_id, post_id, is_gallery=False):
        """
        Send gallery of posts starting with the post with post_id.

        :param chat_id: Chat id to send gallery to.
        :param post_id: Post id to start gallery from.
        :param is_gallery: If True, send gallery of posts. If False, send single post.
            Next and previous buttions will be added to the message if is_gallery is True.
        """
        post_handler = Post(
            mongodb=self.user.db, stackbot=self.user.stackbot,
            post_id=post_id, chat_id=self.user.chat_id,
            is_gallery=is_gallery
        )
        message = self.user.send_message(
            text=post_handler.get_text(),
            reply_markup=post_handler.get_keyboard(),
            delete_after=False,
        )

        # if user asks for this gallery again, we delete the old one to keep the history clean.
        self.user.clean_preview(message.message_id)

        # we should store the callback data for the new message
        self.db.callback_data.update_one(
            {'chat_id': chat_id, 'message_id': message.message_id},
            {'$set': {'post_id': post_id, 'preview': False, 'is_gallery': is_gallery}},
            upsert=True
        )

    def edit_gallery(self, call, next_post_id, is_gallery=False):
        """
        Edit gallery of posts to show next or previous post. Next post to show is the one
        with post_id=next_post_id.

        :param chat_id: Chat id to send gallery to.
        :param next_post_id: post_id of the next post to show.
        :param is_gallery: If True, send gallery of posts. If False, send single post.
            Next and previous buttions will be added to the message if is_gallery is True.
        """
        post_handler = Post(
            mongodb=self.user.db, stackbot=self.user.stackbot,
            post_id=next_post_id, chat_id=self.user.chat_id,
            is_gallery=is_gallery
        )

        self.edit_message(
            call.message.chat.id, call.message.message_id,
            text=post_handler.get_text(),
            reply_markup=post_handler.get_keyboard()
        )

        # we should update the post_id for the buttons cause it is a new post
        self.db.callback_data.update_one(
            {'chat_id': call.message.chat.id, 'message_id': call.message.message_id},
            {'$set': {'post_id': next_post_id, 'preview': False, 'is_gallery': is_gallery}},
        )

    def send_message(self, chat_id, text, reply_markup=None, emojize=True, delete_after=DELETE_BOT_MESSAGES_AFTER_TIME):
        """
        Send message to telegram bot having a chat_id and text_content.

        :param chat_id: Chat id of the user.
        :param text: Text content of the message.
        :param reply_markup: Reply markup of the message.
        :param emojize: Emojize the text.
        :param delete_after: Auto delete message in seconds.
        """
        text = emoji.emojize(text) if emojize else text
        message = self.bot.send_message(chat_id, text, reply_markup=reply_markup)

        if reply_markup == keyboards.main and delete_after is not False:
            delete_after = -1
            prev_doc = self.db.auto_delete.find_one({
                'chat_id': chat_id, 'delete_after': -1
            })
            if prev_doc:
                self.delete_message(chat_id, prev_doc['message_id'])
                db.auto_delete.delete_one({'_id': prev_doc['_id']})

        self.queue_delete_message(chat_id, message.message_id, delete_after)
        return message

    def queue_delete_message(self, chat_id, message_id, delete_after):
        if not delete_after:
            return

        self.db.auto_delete.insert_one({
            'chat_id': chat_id, 'message_id': message_id,
            'delete_after': delete_after, 'created_at': time.time(),
        })

    def edit_message(self, chat_id, message_id, text=None, reply_markup=None, emojize: bool = True):
        """
        Edit telegram message text and/or reply_markup.
        """
        if emojize and text:
            text = emoji.emojize(text)

        # if message text or reply_markup is the same as before, telegram raises an invalid request error
        # so we are doing try/catch to avoid this.
        try:
            if text and reply_markup:
                self.bot.edit_message_text(text=text, reply_markup=reply_markup, chat_id=chat_id, message_id=message_id)
            elif reply_markup:
                self.bot.edit_message_reply_markup(chat_id=chat_id, message_id=message_id, reply_markup=reply_markup)
            elif text:
                self.bot.edit_message_text(text=text, chat_id=chat_id, message_id=message_id)
        except Exception as e:
            logger.debug(e)

    def send_file(self, chat_id, file_unique_id, message_id=None):
        """
        Send file to telegram bot having a chat_id and file_id.
        """
        file_id, content_type, mime_type = self.file_unique_id_to_content(file_unique_id)

        # Send file to user with the appropriate send_file method according to the content_type
        send_method = getattr(self.bot, f'send_{content_type}')
        message = send_method(
            chat_id, file_id,
            reply_to_message_id=message_id,
            caption=f"<code>{mime_type or ''}</code>",
        )

        # Delete message after a while
        self.queue_delete_message(chat_id, message.message_id, DELETE_BOT_MESSAGES_AFTER_TIME)

    def file_unique_id_to_content(self, file_unique_id):
        """
        Get file content having a file_id.
        """
        query_result = self.db.post.find_one({'content.file_unique_id': file_unique_id}, {'content.$': 1})
        if not query_result:
            return

        content = query_result['content'][0]
        return content['file_id'], content['content_type'], content.get('mime_type')

    def delete_message(self, chat_id, message_id):
        """
        Delete bot message.
        """
        try:
            self.bot.delete_message(chat_id, message_id)
        except Exception as e:
            logger.debug('Error deleting message: Message not found.')

    def get_call_info(self, call):
        """
        Get call info from call data.

        Every message with inline keyboard has information stored in database, particularly the post_id.

        We store the post_id in the database to use it later when user click on any inline button.
        For example, if user click on 'answer' button, we know which post_id to store answer for.
        This post_id is stored in the database as 'replied_to_post_id' field.

        We also store post_type in the database to use the right handler in user object (Question, Answer, Comment).
        """
        callback_data = self.db.callback_data.find_one({'chat_id': call.message.chat.id, 'message_id': call.message.message_id})
        return callback_data or {}

    def answer_callback_query(self, call_id, text, emojize=True):
        """
        Answer to a callback query.
        """
        if emojize:
            text = emoji.emojize(text)
        self.bot.answer_callback_query(call_id, text=text)

    def get_settings_keyboard(self):
        """
        Returns settings main menu keyboard.
        """
        muted_bot = self.user.settings.get('muted_bot')
        if muted_bot:
            keys = [inline_keys.change_identity, inline_keys.unmute]
        else:
            keys = [inline_keys.change_identity, inline_keys.mute]

        return create_keyboard(*keys, is_inline=True)

    def get_settings_text(self):
        """
        Returns settings text message.
        """
        text = constants.SETTINGS_START_MESSAGE.format(
            first_name=self.user.first_name,
            username=self.user.username,
            identity=self.user.identity,
        )
        return text

if __name__ == '__main__':
    logger.info('Bot started...')
    stackbot = StackBot(telebot=bot, mongodb=db)
    stackbot.run()
