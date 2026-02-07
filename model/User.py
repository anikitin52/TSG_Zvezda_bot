from model.Enums import UserRole
from services.Database import select_query, insert_query, update_query
from utils.logger import logger


class User:
    def __init__(self, telegram_id):
        self.id = None
        self.telegram_id = telegram_id
        self.apartment = None
        self.roles = []

    # Getters and Setters
    def get_telegram_id(self):
        return self.telegram_id

    def get_apartment(self):
        return self.apartment

    def get_roles(self):
        return self.roles

    def register_in_apartment(self, apartment):
        try:
            self.apartment = apartment

            # Обновляем запись в БД
            update_query('UPDATE users SET apartment = ? WHERE telegram_id = ?',
                         (apartment, self.telegram_id))
            return True
        except Exception as e:
            print('Ошибка в user.register_in_apartment')
            raise Exception

    def change_water(self, meters):
        try:
            update_query('UPDATE users SET water_count = ? WHERE telegram_id = ?',
                         (meters, self.telegram_id))
        except Exception:
            print('Ошибка в user.change_water')
            raise Exception

    def change_electricity(self, meters):
        try:
            update_query('UPDATE users SET electricity_count = ? WHERE telegram_id = ?',
                         (meters, self.telegram_id))
        except Exception:
            print('Ошибка в user.change_electricity')
            raise Exception

    def delete_all_data(self):
        try:
            from services.Database import delete_query

            delete_query('DELETE FROM users WHERE telegram_id = ?', (self.telegram_id,))
            delete_query('DELETE FROM meters_data WHERE telegram_id = ?', (self.telegram_id,))
            delete_query('DELETE FROM appeals WHERE sender_id = ?', (self.telegram_id,))

            # Сбрасываем объект
            self.id = None
            self.apartment = None
            self.roles = []

            return True
        except Exception as e:
            print('Ошибка в user.delete_all_data')
            raise Exception

    def has_role(self, role):
        return role in self.roles

    def create_new_in_db(self, water_count, electricity_count):
        """
        Создает новую запись пользователя в БД со всеми данными
        """
        try:
            user_id = insert_query(
                '''INSERT INTO users (telegram_id, apartment, water_count, electricity_count) 
                   VALUES (?, ?, ?, ?)''',
                (self.telegram_id, self.apartment, water_count, electricity_count)
            )
            self.id = user_id  # Сохраняем присвоенный ID
            return user_id
        except Exception as e:
            print('Ошибка в user.create_new_in_db')
            raise Exception

    def register_as_staff(self, role, name):
        try:
            # Обновляем запись в таблице staff по роли (post)
            update_query('UPDATE staff SET telegram_id = ?, name = ? WHERE post = ?',
                         (self.telegram_id, name, role.value))
            return True
        except Exception as e:
            print('Ошибка в user.register_as_staff')
            raise Exception

    # Служебные методы
    def get_data_from_db(self):
        """
        Загружает из базы данных все доступные данные о пользователе
        Returns:
            Объект User с заполненными полями
        """
        try:
            user = select_query('SELECT * FROM users WHERE telegram_id = ?', (self.telegram_id,))

            if user:
                user_data = user[0]
                self.id = user_data['id']
                self.apartment = user_data['apartment']
                # Если есть квартира - добавляем роль жителя
                if self.apartment:
                    self.roles.append(UserRole.CITIZEN)

            # Проверяем должности в таблице staff
            staff_data = select_query('SELECT post FROM staff WHERE telegram_id = ?', (self.telegram_id,))

            for staff_row in staff_data:
                post = staff_row['post']
                if post == UserRole.ADMIN.value:  # 'admin'
                    self.roles.append(UserRole.ADMIN)
                elif post == UserRole.MANAGER.value:  # 'manager'
                    self.roles.append(UserRole.MANAGER)
                elif post == UserRole.ACCOUNTANT.value:  # 'accountant'
                    self.roles.append(UserRole.ACCOUNTANT)
                elif post == UserRole.PLUMBER.value:  # 'plumber'
                    self.roles.append(UserRole.PLUMBER)
                elif post == UserRole.ELECTRIC.value:  # 'electric'
                    self.roles.append(UserRole.ELECTRIC)

            # Удаляем дубликаты (на всякий случай)
            self.roles = list(dict.fromkeys(self.roles))

            return self

        except Exception as e:
            print('Ошибка в user.get_data_from_db')
            raise Exception


