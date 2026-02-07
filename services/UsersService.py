# services/UserService.py
from services.Database import select_query
from model.User import User


class UserService:
    @staticmethod
    def get_registered_users():
        """Только зарегистрированные пользователи (с квартирой)"""
        users_data = select_query('SELECT telegram_id FROM users WHERE apartment IS NOT NULL', ())
        return [data['telegram_id'] for data in users_data]

    @staticmethod
    def get_sended_data_users(month):
        query = '''
                SELECT DISTINCT telegram_id 
                FROM meters_data 
                WHERE month = ?
            '''
        data = select_query(query, (month,))

        return [row['telegram_id'] for row in data]