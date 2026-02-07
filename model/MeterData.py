from datetime import datetime

from services.Database import select_query
from utils.logger import logger

cold_water_meters = {
    1: ["ХВС"],
    2: ["ХВС-Кухня", "ХВС-Ванная"],
    3: ["ХВС-1", "ХВС-2", "ХВС-3"]
}

hot_water_meters = {
    1: ["ГВС"],
    2: ["ГВС-Кухня", "ГВС-Ванная"],
    3: ["ГВС-1", "ГВС-1", "ГВС-3"]
}

electricity_meters = {
    1: ["Электричество"],
    2: ["Электричество-День", "Электричество-Ночь"]
}


class MeterData:
    def __init__(self, apartment):
        self.apartment = apartment
        self.month = datetime.now().strftime('%m.%Y')  # ММ.ГГГГ
        self.water_count = 0
        self.electricity_type = 0
        self.current_meters = {}
        self.water_meters = []
        self.electricity_meters = []

    def save_to_db(self, user_id, apartment_number, water_count, electricity_type, values_dict):
        """
        Сохраняет показания в базу данных
        values_dict: словарь с показаниями {
            'cold_water_1': значение,
            'hot_water_1': значение,
            'electricity_1': значение,
            ...
        }
        """
        try:
            from services.Database import insert_query

            # Значения по умолчанию
            cw1 = values_dict.get('cold_water_1', 0)
            cw2 = values_dict.get('cold_water_2', 0)
            cw3 = values_dict.get('cold_water_3', 0)
            hw1 = values_dict.get('hot_water_1', 0)
            hw2 = values_dict.get('hot_water_2', 0)
            hw3 = values_dict.get('hot_water_3', 0)
            el1 = values_dict.get('electricity_1', 0)
            el2 = values_dict.get('electricity_2', 0)

            insert_query('''
                INSERT INTO meters_data 
                (telegram_id, apartment, month, type_water_meter, type_electricity_meter,
                 cold_water_1, cold_water_2, cold_water_3,
                 hot_water_1, hot_water_2, hot_water_3,
                 electricity_1, electricity_2)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                user_id, apartment_number, self.month, water_count, electricity_type,
                cw1, cw2, cw3, hw1, hw2, hw3, el1, el2
            ))

            return True
        except Exception as e:
            print('Ошибка в meter_data.save_to_db')
            raise Exception

    def get_apartment(self):
        return int(self.apartment)

    def get_water_count(self):
        return int(self.water_count)

    def check_apartment_send(self):
        try:
            result = select_query('SELECT * FROM meters_data WHERE apartment = ? AND month = ?',
                                  (self.apartment, self.month))
            return len(result) > 0
        except Exception:
            logger.error("Ошибка в MeterData.check_apartment_send")
            raise Exception

    def add_metric(self, counter, value):
        self.metrics[f'c{counter}'] = value

    def all_metrics_entered(self):
        # Холодная вода + горячая вода + электричество
        total_meters = self.water_count * 2  # холодная и горячая вода
        if self.electricity_type == 2:
            total_meters += 2  # два счетчика электричества
        else:
            total_meters += 1  # один счетчик электричества
        return len(self.metrics) == total_meters

    def clear_metrics(self):
        self.metrics = {}

    def get_report(self):
        report_lines = []

        # Холодная вода
        for i in range(self.water_count):
            name = cold_water_meters[self.water_count][i]
            value = self.current_meters.get(str(i + 1), '—')
            report_lines.append(f"{name}: {value}")

        # Горячая вода
        for i in range(self.water_count):
            name = hot_water_meters[self.water_count][i]
            value = self.current_meters.get(str(i + 1 + self.water_count), '—')
            report_lines.append(f"{name}: {value}")

        # Электричество
        elec_meters = electricity_meters[self.electricity_type]
        for i in range(len(elec_meters)):
            name = elec_meters[i]
            value = self.current_meters.get(str(i + 1 + 2 * self.water_count), '—')
            report_lines.append(f"{name}: {value}")

        return "\n".join(report_lines)