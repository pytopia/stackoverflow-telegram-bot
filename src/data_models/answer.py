from bson.objectid import ObjectId
from src.constants import inline_keys, post_status
from src.data_models import Post
from src.utils.keyboard import create_keyboard
from telebot import types


class Answer(Post):
    """
    Class to handle the answers sent by the users to a question.
    """
    def send(self) -> dict:
        """
        Send the answer to the right audience.

        :param post_id: ObjectId of the answer post.
        :return: The answer post.
        """
        post = self.as_dict()

        # Send to the user who asked question
        question = self.db.post.find_one({'_id': ObjectId(post['replied_to_post_id'])})
        question_owner_chat_id = question['chat']['id']

        # Send to Followers
        followers = self.get_followers()

        self.send_to_many(list({self.owner_chat_id, question_owner_chat_id}) + followers)
        return post

    def get_actions_keyboard(self) -> types.InlineKeyboardMarkup:
        """
        Get answer section actions keyboard.

        Keyboard changes depending on the user's role.
        If the user is the owner of the question, he can accept the answer.
        """
        keys, _ = super().get_actions_keys_and_owner()

        answer = self.as_dict()
        question = self.db.post.find_one({'_id': ObjectId(answer['replied_to_post_id'])})
        question_owner_chat_id = question['chat']['id']

        if self.chat_id == question_owner_chat_id:
            keys.append(inline_keys.accept)

        # if post is closed, remove open post only actions from keyboard
        if self.post_status != post_status.OPEN:
            keys = self.remove_closed_post_actions(keys)

        reply_markup = create_keyboard(*keys, is_inline=True)
        return reply_markup
