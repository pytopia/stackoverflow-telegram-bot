class Question:
    def __init__(self, db, stackbot, user):
        self.db = db
        self.stackbot = stackbot
        self.user = user

    def send(self, question_id: str, chat_id: str):
        pass

    def send_to_all(self, question_id: str):
        pass