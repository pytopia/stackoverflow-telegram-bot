import concurrent.futures
import json
from typing import Any, List, Tuple

from bs4 import BeautifulSoup
from bson.objectid import ObjectId
from src import constants
from src.constants import (SUPPORTED_CONTENT_TYPES, inline_keys, post_status,
                           post_types)
from src.data import DATA_DIR
from src.utils.common import (human_readable_size, human_readable_unix_time,
                              json_encoder)
from src.utils.keyboard import create_keyboard
from telebot import types, util


class BasePost:
    """
    General class for all types of posts: Question, Answer, Comment, etc.
    """
    def __init__(
        self, db, stackbot, post_id: str = None, chat_id: str = None,
        is_gallery: bool = False, gallery_filters=None
    ):
        self.db = db
        self.collection = self.db.post
        self.stackbot = stackbot
        self.chat_id = chat_id
        self.supported_content_types = SUPPORTED_CONTENT_TYPES

        # post_id has setter and getter to convert it to ObjectId in case it is a string
        self._post_id = post_id
        self.is_gallery = is_gallery
        self.gallery_filters = gallery_filters

        # Show more and show less buttons
        self.post_text_length_button = None
        self._emoji = constants.EMOJI.get(self.post_type)
        self.html_icon = constants.HTML_ICON.get(self.post_type)

    @property
    def emoji(self):
        return self._emoji

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

        return self.db.post.find_one({'_id': ObjectId(self.post_id)}) or {}

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

    def check_prep_post_limits(self, current_post, new_content):
        # Get current content text and attachments
        text, attachments = self.get_post_text_and_attachments(current_post)

        if new_content.get('text'):
            text += new_content['text']
        if new_content.get('attachments'):
            attachments.append(new_content['attachments'])

        characters_left = constants.POST_CHAR_LIMIT[current_post.get('type', self.post_type)] - len(text)
        if characters_left < 0:
            message_text = constants.MAX_NUMBER_OF_CHARACTERS_MESSAGE.format(
                num_extra_characters=abs(characters_left)
            )
            self.stackbot.send_message(self.chat_id, message_text)
            return False
        elif len(attachments) > constants.ATTACHMENT_LIMIT:
            self.stackbot.send_message(self.chat_id, constants.MAX_NUMBER_OF_ATTACHMENTS_MESSAGE)
            return False

        return True

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
            push_data = {'text': message.html_text}
        else:
            # If content is a file, its file_id, mimetype, etc is saved in database for later use
            # Note that if content is a list, the last one has the highest quality
            content = getattr(message, message.content_type)
            content = vars(content[-1]) if isinstance(content, list) else vars(content)
            content['content_type'] = message.content_type

            # removing non-json-serializable data
            content = self.remove_non_json_data(content)
            push_data = {'attachments': content}

        # Check post limitations (number of characters, number of attachments)
        current_post = self.db.post.find_one({'chat.id': self.chat_id, 'status': post_status.PREP}) or {}
        if not self.check_prep_post_limits(current_post=current_post, new_content=push_data):
            self.post_id = current_post['_id']
            return

        # Save to database
        set_data = {'date': message.date, 'type': self.post_type, 'replied_to_post_id': replied_to_post_id}
        output = self.collection.update_one({'chat.id': message.chat.id, 'status': post_status.PREP}, {
            '$push': push_data, '$set': set_data,
        }, upsert=True)

        self.post_id = output.upserted_id or self.collection.find_one({
            'chat.id': message.chat.id, 'status': post_status.PREP
        })['_id']

    def submit(self) -> str:
        """
        Save post with post_id to database.

        :return: Unique id of the stored post in db.
        """
        post = self.collection.find_one({'chat.id': self.chat_id, 'status': post_status.PREP})
        if not post:
            return

        # Stor raw text for search, keywords, similarity, etc.
        post_text = self.get_post_text(post)
        if len(post_text) < constants.MIN_POST_TEXT_LENGTH:
            self.stackbot.send_message(self.chat_id, constants.MIN_POST_TEXT_LENGTH_MESSAGE)
            return

        # Update post status to OPEN (from PREP)
        self.collection.update_one({'_id': post['_id']}, {'$set': {
            'status': post_status.OPEN, 'raw_text': post_text,
        }})
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

    @staticmethod
    def get_post_text(post):
        post_text = '\n'.join(post.get('text', []))
        return post_text

    @staticmethod
    def get_post_attachments(post):
        return post.get('attachments', [])

    @staticmethod
    def get_post_text_and_attachments(post):
        return BasePost.get_post_text(post), BasePost.get_post_attachments(post)

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

        # prettify message with other information such as sender, post status, etc.
        post_text = self.get_post_text(post)
        untrucated_post_text = post_text

        # Empty post text is allowed (User can send an empty post with attachments)
        if not post_text:
            post_text = constants.EMPTY_QUESTION_TEXT_MESSAGE

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
                num_characters_left = constants.POST_CHAR_LIMIT[post['type']] - len(untrucated_post_text)
                post_text = constants.POST_PREVIEW_MESSAGE.format(
                    post_text=post_text, post_type=post_type, post_id=post['_id'],
                    num_characters_left=num_characters_left
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
        # Add back to original post key
        original_post = self.db.post.find_one({'_id': ObjectId(post['replied_to_post_id'])})
        if original_post:
            keys.append(inline_keys.original_post)
            callback_data.append(inline_keys.original_post)

        attachments = self.get_post_attachments(post)
        if attachments:
            keys.append(f'{inline_keys.attachments} ({len(attachments)})')
            callback_data.append(inline_keys.attachments)

        # Add show comments, answers, etc.
        num_comments = self.db.post.count_documents(
            {'replied_to_post_id': self.post_id, 'type': post_types.COMMENT, 'status': post_status.OPEN})
        num_answers = self.db.post.count_documents(
            {'replied_to_post_id': self.post_id, 'type': post_types.ANSWER, 'status': post_status.OPEN})
        if num_comments:
            keys.append(f'{inline_keys.show_comments} ({num_comments})')
            callback_data.append(inline_keys.show_comments)
        if num_answers:
            keys.append(f'{inline_keys.show_answers} ({num_answers})')
            callback_data.append(inline_keys.show_answers)

        if not preview:
            # Add actions, like, etc. keys
            liked_by_user = self.collection.find_one({'_id': ObjectId(self.post_id), 'likes': self.chat_id})
            like_key = inline_keys.like if liked_by_user else inline_keys.unlike
            num_likes = len(post.get('likes', []))
            new_like_key = f'{like_key} ({num_likes})' if num_likes else like_key

            keys.extend([new_like_key, inline_keys.actions])
            callback_data.extend([inline_keys.like, inline_keys.actions])

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

            print('Adding previous key...')
            print(prev_key)
            callback_data.append(prev_key)

            # Page number key
            post_position_key = f'-- {post_position}/{num_posts} --'
            keys.append(post_position_key)
            callback_data.append(inline_keys.page_number)

            # Next page key
            next_key = inline_keys.next_post if post_position < num_posts else inline_keys.last_page
            keys.append(next_key)
            callback_data.append(next_key)

            # add gallery export key
            keys.append(inline_keys.export_gallery)
            callback_data.append(inline_keys.export_gallery)

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

    def toggle_post_field(self, field: str, field_value: Any) -> None:
        """
        Pull/Push to the collection field of the post.

        :param field: Collection field to be toggled (push/pull)
        """
        exists_flag = self.collection.find_one({'_id': ObjectId(self.post_id), field: field_value})

        if exists_flag:
            self.collection.update_one({'_id': ObjectId(self.post_id)}, {'$pull': {field: field_value}})
        else:
            self.collection.update_one(
                {'_id': ObjectId(self.post_id)}, {'$addToSet': {field: field_value}}
            )

    def follow(self):
        """
        Follow/Unfollow post with post_id.

        :param post_id: Unique id of the post
        """
        self.toggle_post_field('followers', self.chat_id)

    def like(self):
        """
        Like post with post_id or unlike post if already liked.

        :param post_id: Unique id of the post
        """
        self.toggle_post_field('likes', self.chat_id)

    def bookmark(self):
        """
        Like post with post_id or unlike post if already liked.

        :param post_id: Unique id of the post
        """
        self.toggle_post_field('bookmarked_by', self.chat_id)

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

        # Check if post is bookmarked by the user
        bookmarked = self.db.users.find_one({'chat.id': self.chat_id, 'bookmarks': self.post_id})
        if bookmarked:
            keys.append(inline_keys.unbookmark)
        else:
            keys.append(inline_keys.bookmark)

        return keys, owner_chat_id

    def get_attachments_keyboard(self):
        post = self.as_dict()

        keys = [inline_keys.back]
        callback_data = [inline_keys.back]

        # Add attachments
        for attachment in self.get_post_attachments(post):
            # Attachments may have or may not have a file_name attribute.
            # But they always have content_type
            file_name = attachment.get('file_name') or attachment['content_type']
            file_size = human_readable_size(attachment['file_size'])
            keys.append(f"{file_name} - {file_size}")
            callback_data.append(attachment['file_unique_id'])

        return create_keyboard(*keys, callback_data=callback_data, is_inline=True)

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

    def switch_field_between_multiple_values(self, field: str, values: List):
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
        user = User(chat_id=self.owner_chat_id, first_name=None, db=self.db, stackbot=self.stackbot)
        return user.identity

    @staticmethod
    def remove_non_json_data(json_data):
        return json.loads(json.dumps(json_data, default=json_encoder))

    def export(self, format='html'):
        """
        Export post as html
        """
        post = self.as_dict()
        if format == 'html':
            with open(DATA_DIR / 'post_card.html', 'r') as f:
                template_html = f.read()

            replace_map = {
                'emoji': self.html_icon,
                'post_id': post['_id'],
                'post_type': post['type'].title(),
                'text': self.get_text(prettify=False, truncate=False, preview=False),
                'date': human_readable_unix_time(post['date']),
            }
            for key, value in replace_map.items():
                template_html = template_html.replace(r'{{{' + key + r'}}}', str(value))

            return template_html
