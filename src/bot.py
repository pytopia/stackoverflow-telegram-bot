import os

import telebot
from telebot import apihelper

# Middleware handlers
apihelper.ENABLE_MIDDLEWARE = True

# Initialize bot
bot = telebot.TeleBot(
    os.environ['TELEGRAMBOT_TOKEN'], parse_mode='HTML'
)
