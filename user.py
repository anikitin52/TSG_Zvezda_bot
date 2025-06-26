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
        return "\n".join([
            f"Счетчик {i + 1}: {self.metrics.get(f'c{i + 1}', '—')}"
            for i in range(self.meters_count)
        ])