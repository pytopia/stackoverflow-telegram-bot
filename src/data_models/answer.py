from bson.objectid import ObjectId
from src import constants
from src.constants import inline_keys, post_status
from src.data_models.base import BasePost
from src.utils.keyboard import create_keyboard
from telebot import types


class Answer(BasePost):
    """
    Class to handle the answers sent by the users to a question.
    """
    @property
    def question(self) -> dict:
        """
        Get the question of the answer.

        :return: The question of the answer.
        """
        post = self.as_dict()
        return self.db.post.find_one({'_id': ObjectId(post['replied_to_post_id'])})

    @property
    def emoji(self) -> str:
        """
        Get the emoji of the answer.

        :return: The emoji of the answer.
        """
        answer = self.as_dict()
        if self.question.get('accepted_answer') == answer['_id']:
            return ':check_mark_button:'
        else:
            return constants.EMOJI.get(answer['type'])

    @emoji.setter
    def emoji(self, value):
        self.emoji = value

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
            if question.get('accepted_answer') == answer['_id']:
                keys.append(inline_keys.unaccept)
            else:
                keys.append(inline_keys.accept)

        # if post is closed, remove open post only actions from keyboard
        if self.post_status != post_status.OPEN:
            keys = self.remove_closed_post_actions(keys)

        reply_markup = create_keyboard(*keys, is_inline=True)
        return reply_markup

    def accept_answer(self):
        """
        Accept/Unaccept the answer.

        :return: The answer post.
        """
        answer = self.as_dict()
        question = self.db.post.find_one({'_id': ObjectId(answer['replied_to_post_id'])})
        question_owner_chat_id = question['chat']['id']

        # Check if it's already the accepted answer
        if question.get('accepted_answer') == answer['_id']:
            self.db.post.update_one(
                {'_id': question['_id']},
                {'$set': {'status': post_status.OPEN, 'accepted_answer': None}}
            )
        else:
            self.db.post.update_one(
                {'_id': question['_id']},
                {'$set': {'status': post_status.RESOLVED, 'accepted_answer': answer['_id']}}
            )

            # Send to the answer owner that the question is accepted
            answer_owner_chat_id = answer['chat']['id']
            self.stackbot.send_message(answer_owner_chat_id, constants.USER_ANSWER_IS_ACCEPTED_MESSAGE)

            # Send to Audience: Answer and question followers
            answer_followers_chat_id = self.get_followers()
            question_followers_chat_id = question.get('followers', [])
            audience_chat_id = set(question_followers_chat_id).union(answer_followers_chat_id)
            for chat_id in audience_chat_id:
                self.stackbot.send_message(chat_id, constants.NEW_ACCEPTED_ANSWER)

            self.send_to_many(audience_chat_id.union([answer_owner_chat_id]))

        return answer
