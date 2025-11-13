class Apartment:
    def __init__(self, number):
        self.electricity_meters = None
        self.water_meters = None
        self.number = number

    def set_water_meters_count(self, count):
        self.water_meters = count
        
    def set_electricity_count(self, count):
        self.electricity_meters = count