def register_command_handlers(self):
    @self.bot.message_handler(commands=['start'])
    def start(message):
        """
        This handler is called when user sends /start command.

        1. Send Welcome Message
        2. Insert (if user is new, or update) user in database.
        3. Reset user data (settings, state, track data)
        """
        self.user.register(message)
