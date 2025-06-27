from data import cold_water_meters, hot_water_meters, electricity_meters


class User:
    def __init__(self, telegram_id, apartment=None, water_count=1, electricity_type="one_rate"):
        self.telegram_id = telegram_id
        self.apartment = apartment
        self.water_count = water_count
        self.electricity_type = electricity_type
        self.metrics = {}

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
            report_lines.append(f"{cold_water_meters[self.water_count][i]}: {self.metrics.get(f'c{i + 1}', '—')}")

        # Горячая вода (количество счетчиков такое же как у холодной)
        for i in range(self.water_count):
            report_lines.append(
                f"{hot_water_meters[self.water_count][i]}: {self.metrics.get(f'c{i + 1 + self.water_count}', '—')}")

        # Электричество
        elec_meters = electricity_meters[self.electricity_type]
        for i in range(len(elec_meters)):
            report_lines.append(f"{elec_meters[i]}: {self.metrics.get(f'c{i + 1 + 2 * self.water_count}', '—')}")

        return "\n".join(report_lines)