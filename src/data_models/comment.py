from bson.objectid import ObjectId
from src.data_models.post import Post
from src.utils.keyboard import create_keyboard
from telebot import types


class Comment(Post):
    """
    Class to handle the comments sent by the users on other posts.
    """
    def __init__(self, mongodb, stackbot, chat_id: str = None):
        super().__init__(mongodb, stackbot, chat_id=chat_id)
        self.emoji = ':speech_balloon:'
        self.supported_content_types = ['text']

    def send(self, post_id: str) -> dict:
        """
        Send the comment to the right audience.
            - Comment owner.
            - The post owner that comment is replied to.
            - Post followers.

        :param post_id: ObjectId of the comment post.
        :return: The comment post.
        """
        post = self.collection.find_one({'_id': post_id})
        post_owner_chat_id = post['chat']['id']

        # Send to the user who sent the original post
        related_post = self.db.post.find_one({'_id': ObjectId(post['replied_to_post_id'])})
        related_post_owner_chat_id = related_post['chat']['id']

        # Send to Followers
        followers = self.get_followers(post_id)

        self.send_to_many(post_id, list({post_owner_chat_id, related_post_owner_chat_id}) + followers)
        return post

    def get_actions_keyboard(self, post_id: str, chat_id: str) -> types.InlineKeyboardMarkup:
        """
        Get comment section actions keyboard.
        """
        keys, _ = super().get_actions_keys_and_owner(post_id, chat_id)
        reply_markup = create_keyboard(*keys, is_inline=True)
        return reply_markup
