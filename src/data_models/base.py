import concurrent.futures
import json
from typing import List, Tuple

from bs4 import BeautifulSoup
from bson.objectid import ObjectId
from loguru import logger
from src import constants
from src.constants import (SUPPORTED_CONTENT_TYPES, inline_keys, post_status,
                           post_type)
from src.utils.common import (human_readable_size, human_readable_unix_time,
                              json_encoder)
from src.utils.keyboard import create_keyboard
from telebot import types, util


class BasePost:
    """
    General class for all types of posts: Question, Answer, Comment, etc.
    """
    def __init__(
        self, mongodb, stackbot, post_id: str = None, chat_id: str = None,
        is_gallery: bool = False, gallery_filters=None
    ):
        self.db = mongodb
        self.stackbot = stackbot

        # post_id has setter and getter to convert it to ObjectId in case it is a string
        self._post_id = post_id

        self.chat_id = chat_id

        self.is_gallery = is_gallery
        self.gallery_filters = gallery_filters

        self.emoji = constants.EMOJI.get(self.post_type)
        self.collection = self.db.post
        self.supported_content_types = SUPPORTED_CONTENT_TYPES

        self.post_text_length_button = None
        self.is_splitted = True

    @property
    def post_id(self):
        if isinstance(self._post_id, str):
            return ObjectId(self._post_id)
        return self._post_id

    @post_id.setter
    def post_id(self, post_id: str):
        if isinstance(post_id, str):
            self._post_id = ObjectId(post_id)
        else:
            self._post_id = post_id

    def as_dict(self) -> dict:
        if not self.post_id:
            return {}
        post = self.db.post.find_one({'_id': ObjectId(self.post_id)}) or {}
        return post

    @property
    def owner_chat_id(self) -> str:
        return self.as_dict().get('chat', {}).get('id')

    @property
    def post_type(self) -> str:
        post_type = self.as_dict().get('type')
        return post_type or self.__class__.__name__.lower()

    @property
    def post_status(self) -> str:
        return self.as_dict().get('status')

    def update(self, message, replied_to_post_id: str = None) -> str:
        """
        In ask_post state, the user can send a post in multiple messages.
        In each message, we update the current post with the message recieved.

        :param message: Message recieved from the user.
        :param replied_to_post_id: Unique id of the post that the user replied to.
            This is null for questions, but is required for answers and comments.
        :return: Unique id of the stored post in db.
        """
        # If content is text, we store its html version to keep styles (bold, italic, etc.)
        if message.content_type not in self.supported_content_types:
            return

        if message.content_type == 'text':
            content = {'text': message.html_text}
        else:
            # If content is a file, its file_id, mimetype, etc is saved in database for later use
            # Note that if content is a list, the last one has the highest quality
            content = getattr(message, message.content_type)
            content = vars(content[-1]) if isinstance(content, list) else vars(content)
        content['content_type'] = message.content_type

        # removing non-json-serializable data
        content = self.remove_non_json_data(content)

        # Save to database
        set_data = {'date': message.date, 'type': self.post_type, 'replied_to_post_id': replied_to_post_id}
        output = self.collection.update_one({'chat.id': message.chat.id, 'status': post_status.PREP}, {
            '$push': {'content': content},
            '$set': set_data,
        }, upsert=True)

        _id = output.upserted_id or self.collection.find_one({
            'chat.id': message.chat.id, 'status': post_status.PREP
        })['_id']

        self.post_id = _id
        return _id

    def submit(self) -> str:
        """
        Save post with post_id to database.

        :return: Unique id of the stored post in db.
        """
        post = self.collection.find_one({'chat.id': self.chat_id, 'status': post_status.PREP})
        if not post:
            return

        self.collection.update_one({'_id': post['_id']}, {'$set': {'status': post_status.OPEN}})
        return post['_id']

    def send_to_one(self, chat_id: str, preview: bool = False) -> types.Message:
        """
        Send post to user with chat_id.

        :param chat_id: Unique id of the user
        :param preview: If True, send post in preview mode. Default is False.
        :return: Message sent to user.
        """
        post_text, post_keyboard = self.get_text_and_keyboard(preview=preview)

        # If post is sent to a user, then we should automatically update
        # it once in while to keep it fresh, for example, update number of likes.
        auto_update = not preview

        # Preview to user mode or send to other users
        sent_message = self.stackbot.send_message(
            chat_id=chat_id, text=post_text,
            reply_markup=post_keyboard,
            delete_after=False,
            auto_update=auto_update,
        )

        return sent_message

    def send_to_many(self, chat_ids: list) -> types.Message:
        """
        Send post to all users.

        :param chat_ids: List of unique ids of the users.
        :return: Message sent to users.
        """
        with concurrent.futures.ThreadPoolExecutor() as executor:
            for chat_id in chat_ids:
                sent_message = executor.submit(self.send_to_one, chat_id)

        return sent_message

    def send_to_all(self) -> types.Message:
        """
        Send post with post_id to all users.

        :param post_id: Unique id of the post.
        :return: Message sent to users.
        """
        chat_ids = list(map(lambda user: user['chat']['id'], self.db.users.find()))
        return self.send_to_many(chat_ids)

    def get_text(self, preview: bool = False, prettify: bool = True, truncate: bool = True) -> str:
        """
        Get post text.

        :param preview: If True, send post in preview mode. Default is False.
            - In preview mode, we add help information for user such as how to send the post.
        :param prettify: If True, prettify the text. Default is True.
            - Prettify adds extra information such as post type, from_user, date, etc.
        :return: Post text.
        """
        post = self.as_dict()
        post_text = ""
        for content in post['content']:
            if content['content_type'] == 'text' and content['text']:
                post_text += f"{content['text']}\n"

        # Empty post text is allowed (User can send an empty post with attachments)
        if not post_text:
            post_text = constants.EMPTY_QUESTION_TEXT_MESSAGE

        # prettify message with other information such as sender, post status, etc.
        post_text = post_text.strip()

        # Splits one string into multiple strings, with a maximum amount of `chars_per_string` (max. 4096)
        # Splits by last '\n', '. ' or ' ' in exactly this priority.
        # smart_split returns a list with the splitted text.
        splitted_text = util.smart_split(post_text, chars_per_string=constants.MESSAGE_SPLIT_CHAR_LIMIT)
        if truncate and len(splitted_text) > 1:
            post_text = splitted_text[0]
            # If we truncate the text, some html tags may become unclosed resulting in
            # parsing html error. We therfore use beautifulsoup to close the tags.
            soup = BeautifulSoup(post_text, 'html.parser')
            post_text = soup.prettify()

            self.post_text_length_button = inline_keys.show_more

        elif not truncate and len(splitted_text) > 1:
            self.post_text_length_button = inline_keys.show_less

        # Prettify adds extra information such as post type, from_user, date, etc.
        # Otherwise only raw text is returned.
        if prettify:
            post_type = post['type'].title()
            if preview:
                post_text = constants.POST_PREVIEW_MESSAGE.format(
                    post_text=post_text, post_type=post_type, post_id=post['_id']
                )
            else:
                from_user = self.get_post_owner_identity()
                post_text = constants.SEND_POST_TO_ALL_MESSAGE.format(
                    from_user=from_user, post_text=post_text, post_status=post['status'], post_type=post_type,
                    emoji=self.emoji, date=human_readable_unix_time(post['date']), post_id=post['_id'],
                )

        return post_text

    def get_keyboard(self, preview: bool = False, truncate: bool = True) -> types.InlineKeyboardMarkup:
        """
        Get post keyboard that has attached files + other actions on post such as like, actions menu, etc.

        :param preview: If True, send post in preview mode. Default is False.
            - In preview mode, there is no actions button.
        :return: Post keyboard.
        """
        post = self.as_dict()

        keys, callback_data = [], []
        # add back to original post key
        original_post = self.db.post.find_one({'_id': ObjectId(post['replied_to_post_id'])})
        if original_post:
            keys.append(inline_keys.original_post)
            callback_data.append(inline_keys.original_post)

        # add attachments
        for content in post['content']:
            if content['content_type'] != 'text':
                file_name = content.get('file_name') or content['content_type']
                file_size = human_readable_size(content['file_size'])
                keys.append(f"{file_name} - {file_size}")
                callback_data.append(content['file_unique_id'])

        # add show comments, answers, etc.
        num_comments = self.db.post.count_documents(
            {'replied_to_post_id': self.post_id, 'type': post_type.COMMENT, 'status': post_status.OPEN})
        num_answers = self.db.post.count_documents(
            {'replied_to_post_id': self.post_id, 'type': post_type.ANSWER, 'status': post_status.OPEN})
        if num_comments:
            keys.append(f'{inline_keys.show_comments} ({num_comments})')
            callback_data.append(inline_keys.show_comments)
        if num_answers:
            keys.append(f'{inline_keys.show_answers} ({num_answers})')
            callback_data.append(inline_keys.show_answers)

        if not preview:
            # add actions, like, etc. keys
            liked_by_user = self.collection.find_one({'_id': ObjectId(self.post_id), 'likes': self.chat_id})
            like_key = inline_keys.like if liked_by_user else inline_keys.unlike
            num_likes = len(post.get('likes', []))
            new_like_key = f'{like_key} ({num_likes})' if num_likes else like_key

            keys.extend([new_like_key, inline_keys.actions])
            callback_data.extend([inline_keys.like, inline_keys.actions])

        # call get text to set is_splitted
        self.get_text(preview=preview, truncate=truncate)
        if self.post_text_length_button:
            keys.append(self.post_text_length_button)
            callback_data.append(self.post_text_length_button)

        if self.is_gallery:
            # A gallery post is a post that has more than one post and user
            # can choose to go to next or previous post.

            # Find current page number
            conditions = self.gallery_filters.copy()
            num_posts = self.db.post.count_documents(conditions)

            conditions.update({'date': {'$lt': post['date']}})
            post_position = self.db.post.count_documents(conditions) + 1

            # Previous page key
            prev_key = inline_keys.prev_post if post_position > 1 else inline_keys.first_page
            keys.append(prev_key)
            callback_data.append(prev_key)

            # Page number key
            post_position_key = f'-- {post_position}/{num_posts} --'
            keys.append(post_position_key)
            callback_data.append('Page Number')

            # Next page key
            next_key = inline_keys.next_post if post_position < num_posts else inline_keys.last_page
            keys.append(next_key)
            callback_data.append(next_key)

        post_keyboard = create_keyboard(*keys, callback_data=callback_data, is_inline=True)
        return post_keyboard

    def get_text_and_keyboard(self, preview=False, prettify: bool = True, truncate: bool = True):
        return self.get_text(preview, prettify, truncate), self.get_keyboard(preview, truncate)

    def get_followers(self) -> list:
        """
        Get all followers of the current post.

        :return: List of unique ids of the followers.
        """
        return self.as_dict().get('followers', [])

    def toggle(self, key: str) -> None:
        """
        Pull/Push use to the collection key of the post.

        :param key: Collection key to be toggled (push/pull)
        """
        exists_flag = self.collection.find_one({'_id': ObjectId(self.post_id), key: self.chat_id})

        if exists_flag:
            self.collection.update_one({'_id': ObjectId(self.post_id)}, {'$pull': {key: self.chat_id}})
        else:
            self.collection.update_one(
                {'_id': ObjectId(self.post_id)}, {'$addToSet': {key: self.chat_id}}
            )

    def follow(self):
        """
        Follow/Unfollow post with post_id.

        :param post_id: Unique id of the post
        """
        self.toggle('followers')

    def like(self):
        """
        Like post with post_id or unlike post if already liked.

        :param post_id: Unique id of the post
        """
        self.toggle('likes')

    def get_actions_keys_and_owner(self) -> Tuple[List, str]:
        """
        Get general actions keys and owner of the post. Every post has:
            - back
            - comment
            - edit (for owner only)
            - follow/unfollow (for non-owner users only)
            - open/close (for owner only)

        :param post_id: Unique id of the post
        :param chat_id: Unique id of the user
        :return: List of actions keys and owner of the post.
        """
        post = self.as_dict()
        owner_chat_id = post['chat']['id']

        # every user can comment
        keys = [inline_keys.back]

        # comment is allowed only on open questions
        if post['status'] == post_status.OPEN:
            keys.append(inline_keys.comment)

        # non-owner users can follow/unfollow post
        if self.chat_id != owner_chat_id:
            if self.chat_id in post.get('followers', []):
                keys.append(inline_keys.unfollow)
            else:
                keys.append(inline_keys.follow)

        # post owners can edit, delete, open/close post.
        if self.chat_id == owner_chat_id:
            keys.append(inline_keys.edit)

            current_status = post['status']
            if current_status == post_status.DELETED:
                keys.append(inline_keys.undelete)
            else:
                keys.append(inline_keys.delete)
                if current_status == post_status.OPEN:
                    keys.append(inline_keys.close)
                elif current_status == post_status.CLOSED:
                    keys.append(inline_keys.open)

        return keys, owner_chat_id

    def remove_closed_post_actions(self, keys) -> List:
        """
        Remove actions keys if post is closed.

        :param keys: List of actions keys
        :return: List of actions keys
        """
        new_keys = []
        for key in keys:
            if key in constants.OPEN_POST_ONLY_ACITONS:
                continue
            new_keys.append(key)

        return new_keys

    def toggle_field_values(self, field: str, values: List):
        """
        Close/Open post.
        Nobody can comment/answer to a closed post.
        """
        current_field_value = self.as_dict()[field]
        new_index = values.index(current_field_value) - 1

        self.collection.update_one(
            {'_id': ObjectId(self.post_id)},
            {'$set': {field: values[new_index]}}
        )

    def get_post_owner_identity(self) -> str:
        """
        Return user identity.
        User identity can be 'anonymous', 'usrname', 'first_name'.

        :param chat_id: Unique id of the user
        """
        from src.user import User
        user = User(chat_id=self.owner_chat_id, first_name=None, mongodb=self.db, stackbot=self.stackbot)
        return user.identity

    @staticmethod
    def remove_non_json_data(json_data):
        return json.loads(json.dumps(json_data, default=json_encoder))
