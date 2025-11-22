from data.database import *
from services.exel_export import send_table, send_appeals_table


def export_data(bot):
    @bot.message_handler(commands=['export'])
    def export_data(message):
        """
        Обработка команды /export -> Отправка пользователю таблицы с данными
        :param message: Сообщение от пользователя - команда -> /export
        :return: None
        """
        # Получаем ID пользователей, которым доступна команда
        ACCOUNTANT_ID = find_staff_id('Бухгалтер')
        ADMIN_ID = find_staff_id("Админ")
        MANAGER_ID = find_staff_id("Председатель")
        allowed_users_id = [ACCOUNTANT_ID, ADMIN_ID, MANAGER_ID]

        # Проверяем доступность команды для пользователя
        user_telegram_id = message.chat.id
        if user_telegram_id not in allowed_users_id:
            # Доступа нет -> Отказ в отправке
            bot.send_message(message.chat.id, "❌ У вас нет доступа к этой команде")
            logger.info(
                f'Пользователь {user_telegram_id} попытался экспортировать показания счетчиков. Команда недоступна')
            return
        else:
            # Доступ есть -> Отправляем таблицу
            send_table(user_telegram_id)
            logger.info(f'Пользоватлель {message.chat.id} экспортировал Exel-таблицу с показаниями счетчтков')

    @bot.message_handler(commands=['appeals'])
    def send_appeals(message):
        # Получаем ID пользователей, которым доступна команда
        MANAGER_ID = find_staff_id('Председатель')
        ADMIN_ID = find_staff_id("Админ")
        allowed_users = [MANAGER_ID, ADMIN_ID]

        # Проверяем доступность команды для пользователя
        user_telegram_id = message.from_user.id
        if user_telegram_id not in allowed_users:
            bot.send_message(message.chat.id, "❌ У вас нет доступа к этой команде")
            logger.info(
                f'Пользователь {user_telegram_id} попытался экспортировать табблицу обращений. Команда недоступна')
            return
        else:
            send_appeals_table(user_telegram_id)
            logger.info(f'Пользоватлель {message.chat.id} экспортировал Exel-таблицу с обращениями')
