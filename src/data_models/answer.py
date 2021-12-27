from bson.objectid import ObjectId
from src.constants import inline_keys, post_status
from src.utils.keyboard import create_keyboard

from data_models.post import Post


class Answer(Post):
    """
    Class to handle the answers sent by the users to a question.
    """
    def __init__(self, mongodb, stackbot, chat_id=None):
        super().__init__(mongodb, stackbot, chat_id=chat_id)
        self.emoji = ':bright_button:'

    def submit(self):
        post = super().submit()
        if not post:
            return

        # Send to the user who asked question
        question_owner = self.db.users.find_one({'chat.id': post['chat']['id']})

        # TODO: Send to the user who follows the question
        # question_followers_chat_id = []
        self.send_to_one(post['_id'], question_owner['chat']['id'])
        return post

    def get_actions_keyboard(self, post_id, chat_id):
        keys, _ = super().get_actions_keys_and_owner(post_id, chat_id)

        answer = self.collection.find_one({'_id': post_id})
        question = self.db.question.find_one({'_id': ObjectId(answer['question_id'])})
        question_owner_chat_id = question['chat']['id']

        if chat_id == question_owner_chat_id:
            keys.append(inline_keys.accept)

        reply_markup = create_keyboard(*keys, is_inline=True)
        return reply_markup
