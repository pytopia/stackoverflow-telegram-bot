from bson.objectid import ObjectId
from src.data_models.post import Post
from src.constants import inline_keys
from src.utils.keyboard import create_keyboard


class Comment(Post):
    def __init__(self, mongodb, stackbot, chat_id=None):
        super().__init__(mongodb, stackbot, chat_id=chat_id)
        self.emoji = ':speech_balloon:'
        self.supported_content_types = ['text']

    def submit(self):
        post = super().submit()
        if not post:
            return

        # Send to the user who asked question
        comment_owner = self.db.users.find_one({'chat.id': post['chat']['id']})

        # TODO: Send to the user who follows the question
        # question_followers_chat_id = []
        self.send_to_one(post['_id'], comment_owner['chat']['id'])
        return post

    def get_actions_keyboard(self, post_id, chat_id):
        comment = self.collection.find_one({'_id': post_id})
        comment_owner_chat_id = comment['chat']['id']

        # TODO: Send customized keyboard for the comment owner
        # post = self.db.question.find_one({'_id': ObjectId(comment['post_id'])})
        # post_owner_chat_id = post['chat']['id']

        keys = [inline_keys.back, inline_keys.follow, inline_keys.comment]
        if chat_id == comment_owner_chat_id:
            keys.append(inline_keys.edit)

        reply_markup = create_keyboard(*keys, is_inline=True)
        return reply_markup
