from services.Database import select_query
from utils.logger import logger


def citizens_string_to_list(string_list):
    if not string_list:
        return []
    result = []
    parts = string_list.split()
    for part in parts:
        result.append(part)
    return result


class Apartment:
    def __init__(self, number):
        self.number = number
        self.citizens = []
        self.water_count = 0
        self.electricity_count = 0

    def get_number(self):
        return self.number

    def get_water_count(self):
        return self.water_count

    def get_electricity_count(self):
        return self.electricity_count

    def set_water_meters(self, count):
        self.water_count = count

    def get_data_from_db(self):
        try:
            apartment = select_query('SELECT water_count, electricity_count FROM users WHERE apartment = ? LIMIT 1',
                                     (self.number,))

            if not apartment:
                return self
            apartment_data = apartment[0]
            if apartment_data:
                self.water_count = apartment_data['water_count']
                self.electricity_count = apartment_data['electricity_count']
            return self

        except Exception as e:
            print('Ошибка в apartment.get_data_from_db')
            raise Exception

    def check_apartment_in_db(self):
        """
        Проверяет наличие квартиры в базе данных
        Returns:
            True - квартира найдена
            False - квартира не найдена
        """
        try:
            # Проверяем наличие квартиры в таблице users
            result = select_query('SELECT apartment FROM users WHERE apartment = ? LIMIT 1',
                                  (self.number,))

            # Если есть хотя бы одна запись - квартира существует
            if result:
                # Загружаем данные счетчиков
                user_data = select_query('SELECT water_count, electricity_count FROM users WHERE apartment = ? LIMIT 1',
                                         (self.number,))
                if user_data:
                    data = user_data[0]
                    self.water_count = data.get('water_count', 0)
                    self.electricity_count = data.get('electricity_count', 0)
                return True
            else:
                return False

        except Exception as e:
            print('Ошибка в apartment.check_apartment_in_db')
            raise Exception

    def is_full_data(self):
        return self.water_count in [1, 2, 3] and self.electricity_count in [1, 2] and self.citizens is not []
