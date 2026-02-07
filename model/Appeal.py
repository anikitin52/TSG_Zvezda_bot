from services.Database import insert_query, select_query, update_query


class Appeal:
    def __init__(self, sender_id, apartment, text, post):
        self.id = None
        self.sender_id = sender_id
        self.apartment = apartment
        self.message_text = text
        self.recipient_post = post
        self.answer_text = None
        self.status = 'open'

    def get_data_from_db(self, appeal_id):
        try:
            data = select_query('SELECT * FROM appeals WHERE id = ?', (appeal_id,))
            if not data:
                return None

            data = data[0]
            self.id = data['id']
            self.sender_id = data['sender_id']
            self.apartment = data['apartment']
            self.message_text = data['message_text']
            self.recipient_post = data['recipient_post']
            self.answer_text = data['answer_text']
            self.status = data['status']

            return self
        except Exception as e:

            raise Exception


    def save_to_db(self):
        self.id = insert_query(
            '''INSERT INTO appeals (sender_id, apartment, name, message_text, recipient_post, status) 
               VALUES (?, ?, ?, ?, ?, ?)''',
            (self.sender_id, self.apartment, self.get_sender_name(),
             self.message_text, self.recipient_post, self.status)
        )
        return self.id

    def get_sender_name(self):
        user_data = select_query('SELECT name FROM users WHERE telegram_id = ?', (self.sender_id,))
        return user_data[0]['name'] if user_data else "Неизвестно"


    def set_answer(self, answer_text):
        self.answer_text = answer_text
        self.status = 'closed'



    def update_in_db(self):
        """Обновляет обращение в БД"""

        update_query(
            '''UPDATE appeals 
               SET answer_text = ?, status = ? 
               WHERE id = ?''',
            (self.answer_text, self.status, self.id)
        )
