from data import cold_water_meters, hot_water_meters, electricity_meters


class User:
    def __init__(self, telegram_id, apartment=None, cold_water_count=1, electricity_type="one_rate"):
        self.telegram_id = telegram_id
        self.apartment = apartment
        self.cold_water_count = cold_water_count
        self.electricity_type = electricity_type
        self.metrics = {}

    def add_metric(self, counter, value):
        self.metrics[f'c{counter}'] = value

    def all_metrics_entered(self):
        total_meters = self.cold_water_count + self.cold_water_count + (1 if self.electricity_type == "one_rate" else 2)
        return len(self.metrics) == total_meters

    def clear_metrics(self):
        self.metrics = {}

    def get_report(self):
        report_lines = []

        # Холодная вода
        for i in range(self.cold_water_count):
            report_lines.append(f"{cold_water_meters[self.cold_water_count][i]}: {self.metrics.get(f'c{i + 1}', '—')}")

        # Горячая вода (количество счетчиков такое же как у холодной)
        for i in range(self.cold_water_count):
            report_lines.append(
                f"{hot_water_meters[self.cold_water_count][i]}: {self.metrics.get(f'c{i + 1 + self.cold_water_count}', '—')}")

        # Электричество
        elec_meters = electricity_meters[self.electricity_type]
        for i in range(len(elec_meters)):
            report_lines.append(f"{elec_meters[i]}: {self.metrics.get(f'c{i + 1 + 2 * self.cold_water_count}', '—')}")

        return "\n".join(report_lines)