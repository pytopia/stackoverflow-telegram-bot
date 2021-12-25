import concurrent.futures
from itertools import repeat

from bson.objectid import ObjectId

import constants
from src.constants import inline_keys, post_status
from src.utils.common import human_readable_size
from src.utils.keyboard import create_keyboard


class Post:
    """
    Main class to handle posts and their actions.
    """
    def __init__(self, mongodb, stackbot, post_type='question'):
        self.db = mongodb
        self.stackbot = stackbot
        self.post_type = post_type
        self.collection = getattr(self.db, post_type)

    def update(self, message):
        """
        In ask_post state, the user can send a post in multiple messages.
        In each message, we update the current post with the message recieved.
        """
        # If content is text, we store its html version to keep styles (bold, italic, etc.)
        if message.content_type == 'text':
            content = {'text': message.html_text}
        else:
            # If content is a file, its file_id, mimetype, etc is saved in database for later use
            # Note that if content is a list, the last one has the highest quality
            content = getattr(message, message.content_type)
            content = vars(content[-1]) if isinstance(content, list) else vars(content)
        content['content_type'] = message.content_type

        # Save
        output = self.collection.update_one({'chat.id': message.chat.id, 'status': post_status.PREP}, {
            '$push': {'content': content},
            '$set': {'date': message.date},
        }, upsert=True)

        _id = output.upserted_id or self.collection.find_one({
            'chat.id': message.chat.id, 'status': post_status.PREP
        })['_id']
        return _id

    def save(self, post_id: str):
        """
        Save post with post_id to database.
        """
        self.collection.update_one({'_id': post_id}, {'$set': {'status': post_status.SENT}})

    def send_to_one(self, post_id: str, chat_id: str, preview: bool = False):
        """
        Send post with post_id to user with chat_id.

        :param post_id: Unique id of the post
        :param chat_id: Unique id of the user
        :param preview: If True, send post in preview mode. Default is False.
        """
        post_keyboard = self.get_post_keyboard(post_id)
        post_text = self.get_post_text(post_id)

        # Preview to user mode or send to other users
        if preview:
            post_formatted_text = constants.QUESTION_PREVIEW_MESSAGE.format(question=post_text)
        else:
            post_formatted_text = constants.SEND_QUESTION_TO_ALL_MESSAGE.format(
                from_user=chat_id, question=post_text
            )
        message = self.stackbot.send_message(
            chat_id=chat_id, text=post_formatted_text,
            reply_markup=post_keyboard
        )

        self.db.callback_data.insert_one({
            'post_id': post_id,
            'chat_id': chat_id,
            'message_id': message.message_id,
            'type': self.post_type,
        })

    def send_to_all(self, post_id: str):
        """
        Send post with post_id to all users.
        """
        chat_ids = map(lambda user: user['chat']['id'], self.db.users.find())
        with concurrent.futures.ThreadPoolExecutor() as executor:
            executor.map(self.send_to_one, repeat(post_id), chat_ids)

    def get_post_text(self, post_id: str):
        """
        Get post text with post_id.

        :param post_id: Unique id of the post
        :return: Post text.
        """
        post = self.collection.find_one({'_id': ObjectId(post_id)})
        post_text = ""
        for content in post['content']:
            if content['content_type'] == 'text':
                post_text += f"{content['text']}\n"

        # Empty post text is allowed (User can send an empty post with attachments)
        if not post_text:
            post_text = constants.EMPTY_QUESTION_TEXT_MESSAGE

        return post_text

    def get_post_keyboard(self, post_id):
        """
        Get post keyboard that has attached files + other actions on post such as like, actions menu, etc.
        """
        post = self.collection.find_one({'_id': ObjectId(post_id)})

        # get default keys
        keys, callback_data = [], []
        post_keyboard = None
        for content in post['content']:
            if content['content_type'] != 'text':
                file_name = content.get('file_name') or content['content_type']
                file_size = human_readable_size(content['file_size'])
                keys.append(f"{file_name} - {file_size}")
                callback_data.append(content['file_unique_id'])

        # add actions, like, etc. keys
        num_likes = len(post.get('likes', []))
        like_key_text = '' if num_likes == 0 else f'{inline_keys.like} {num_likes}'

        keys.extend([inline_keys.actions, like_key_text or inline_keys.like])
        callback_data.extend([inline_keys.actions, inline_keys.like])

        post_keyboard = create_keyboard(*keys, callback_data=callback_data, is_inline=True)
        return post_keyboard

    def like(self, chat_id, post_id):
        """
        Like post with post_id.
        """
        self.collection.update_one(
            {'_id': ObjectId(post_id)}, {'$push': {'likes': chat_id}}
        )
