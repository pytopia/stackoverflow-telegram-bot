from bson.objectid import ObjectId
from src.constants import post_status
from src.data_models.base import BasePost
from src.utils.keyboard import create_keyboard
from telebot import types


class Comment(BasePost):
    """
    Class to handle the comments sent by the users on other posts.
    """
    def __init__(
        self, db, stackbot, post_id: str = None, chat_id: str = None,
        is_gallery: bool = False, gallery_filters=None
    ):
        super().__init__(
            db=db, stackbot=stackbot, chat_id=chat_id, post_id=post_id,
            is_gallery=is_gallery, gallery_filters=gallery_filters
        )
        self.supported_content_types = ['text']

    def send(self) -> dict:
        """
        Send the comment to the right audience.
            - Comment owner.
            - The post owner that comment is replied to.
            - Post followers.

        :param post_id: ObjectId of the comment post.
        :return: The comment post.
        """
        post = self.as_dict()

        # Send to the user who sent the original post
        related_post = self.db.post.find_one({'_id': ObjectId(post['replied_to_post_id'])})
        related_post_owner_chat_id = related_post['chat']['id']

        # Send to Followers
        followers = self.get_followers()

        self.send_to_many(list({self.owner_chat_id, related_post_owner_chat_id}) + followers)
        return post

    def get_actions_keyboard(self) -> types.InlineKeyboardMarkup:
        """
        Get comment section actions keyboard.
        """
        keys, _ = super().get_actions_keys_and_owner()

        # if post is closed, remove open post only actions from keyboard
        if self.post_status != post_status.OPEN:
            keys = self.remove_closed_post_actions(keys)

        reply_markup = create_keyboard(*keys, is_inline=True)
        return reply_markup
