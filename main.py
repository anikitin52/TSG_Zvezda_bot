import sys

from ui.telegram.bot import run_telegram_bot
from services.Database import init_db, init_staff
from utils.logger import logger


def main():
    """
    Основная функция запуска сервиса
    """
    print('Сервис TSG Zvezda bot запущен')
    logger.info("Сервис запущен")

    # Инициаллизация базы данных
    try:
        init_db()
        init_staff()
    except Exception as e:
        logger.error("Сервис остановлен по причине ошибки")
        print('Сервис остановлен')
        sys.exit(1)

    # Запуск Telegram-бота
    run_telegram_bot()


if __name__ == '__main__':
    main()

