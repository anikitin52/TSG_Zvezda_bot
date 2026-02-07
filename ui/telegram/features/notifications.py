from datetime import datetime
import time

from model.User import User
from utils.backup import make_backup
from services.TimeManager import TimeManager
from services.UsersService import UserService
from services.SecurityManager import SecurityManager
from services.ExportManager import ExportManager
from utils.logger import logger

time_manager = TimeManager()
user_service = UserService()
security_manager = SecurityManager()
export_manager = ExportManager()


def notifications(bot):
    """
    Обработчик напоминаний
    """
    print("Напоминания запущены")
    last_backup_day = None

    while True:
        now = datetime.now()
        current_month = f"{now.month}.{now.year}"
        current_day = now.day
        current_hour = now.hour
        current_minute = now.minute

        # Ежедневный бэкап в 2:00
        if current_day % 5 == 0 and current_hour == 2 and current_minute == 0:
            if last_backup_day != current_day:
                make_backup()
                last_backup_day = current_day
                logger.info("Создан ежедневный бэкап")

        # Начало сбора показаний
        if (current_day == time_manager.get_start_day() and
                current_hour == time_manager.get_start_hour() and
                current_minute == 43):

            users = user_service.get_registered_users()  # список telegram_id
            logger.info("Открыт сбор показаний счетчиков")

            for user_id in users:  # user_id - число
                bot.send_message(user_id, "📬 Открыт сбор показаний счетчиков")

        # Напоминание о передаче
        if (current_day == time_manager.get_notification_day() and
                current_hour == time_manager.get_notification_hour() and
                current_minute == 44):

            users = user_service.get_registered_users()  # список telegram_id
            sended_data = user_service.get_sended_data_users(current_month)

            apartments = [data[2] for data in sended_data]

            for user_id in users:
                user = User(user_id).get_data_from_db()
                if user and user.apartment not in apartments:
                    bot.send_message(user_id, "⏰ Пора передать показания счетчиков! /send")
                    logger.info(f"Напоминание отправлено пользователю {user_id}")

        # Завершение сбора
        if (current_day == time_manager.get_end_day() and
                current_hour == time_manager.get_end_hour() and
                current_minute == 45):
            users = user_service.get_registered_users()  # список telegram_id
            sended_data = user_service.get_sended_data_users(current_month)

            apartments = [data[2] for data in sended_data]

            for user_id in users:
                user = User(user_id).get_data_from_db()
                if user and user.apartment not in apartments:
                    bot.send_message(user_id, "❌ Прием показаний счетсчков закрыт /send")
                    logger.info(f"Напоминание отправлено пользователю {user_id}")

            ACCOUNTANT_ID = security_manager.get_staff_id('Бухгалтер')
            export_manager.export_meters_data()

            now = datetime.now()
            current_month = f"{now.month:02d}.{now.year}"

            with open(f"Показания счетчиков {current_month}.xlsx", "rb") as f:
                bot.send_document(ACCOUNTANT_ID, f)

            logger.info('Таблица отправлена бухгалтеру')
            make_backup()

        time.sleep(60)