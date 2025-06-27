from data import meters4, meters6
class User:
    def __init__(self, telegram_id, apartment=None, meters_count=0):
        self.telegram_id = telegram_id
        self.apartment = apartment
        self.meters_count = meters_count
        self.metrics = {}

    def add_metric(self, counter, value):
        self.metrics[f'c{counter}'] = value

    def all_metrics_entered(self):
        return len(self.metrics) == self.meters_count

    def clear_metrics(self):
        self.metrics = {}

    def get_report(self):
        if self.meters_count == 4:
            meters = meters4
        elif self.meters_count == 6:
            meters = meters6
        else:
            return "Ошибка: неизвестное количество счётчиков"

        return "\n".join([
            f"{meters[i]}: {self.metrics.get(f'c{i + 1}', '—')}"
            for i in range(self.meters_count)
        ])
