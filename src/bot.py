import os
import telebot


# Initialize bot
bot = telebot.TeleBot(
    os.environ['TELEGRAMBOT_TOKEN'], parse_mode='HTML'
)
