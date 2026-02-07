import os


class TimeManager:
    def __init__(self):
        self.__start_collection_day = os.getenv('START_COLLECTION_DAY')
        self.__end_collection_day = os.getenv('END_COLLECTION_DAY')
        self.__notification_day = os.getenv('NOTIFICATION_DAY')
        self.__start_hour = os.getenv('START_COLLECTION_HOUR')
        self.__notification_hour = os.getenv('NOTIFICATION_HOUR')
        self.__end_hour = os.getenv('END_HOUR')
        self.__months = months = {
            1: 'январь', 2: 'февраль', 3: 'март', 4: 'апрель',
            5: 'май', 6: 'июнь', 7: 'июль', 8: 'август',
            9: 'сентябрь', 10: 'октябрь', 11: 'ноябрь', 12: 'декабрь'
        }

    def get_start_day(self):
        return int(self.__start_collection_day)

    def get_start_hour(self):
        return int(self.__start_hour)

    def get_end_day(self):
        return int(self.__end_collection_day)

    def get_notification_day(self):
        return int(self.__notification_day)

    def get_notification_hour(self):
        return int(self.__notification_hour)

    def get_end_hour(self):
        return int(self.__end_hour)

    def get_text_month(self, month_number):
        return self.__months[month_number]
