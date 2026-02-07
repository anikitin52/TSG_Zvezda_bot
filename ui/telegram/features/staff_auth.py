from services.SecurityManager import SecurityManager
from model.Enums import UserRole
from model.User import User
from utils.logger import logger

manager = SecurityManager()


def add_enter_code(message, bot, user):
    try:
        code = message.text
        if code == manager.get_enter_code():
            msg = bot.send_message(message.chat.id, "Bведите код авторизации")
            bot.register_next_step_handler(msg, lambda m: check_auth_code(m, bot, user))

        elif message.text.strip().lower() == '/cancel':
            bot.send_message(message.chat.id, "❌ Действие отменено")
            return

        else:
            msg = bot.send_message(message.chat.id, "❌ Неверный пароль. Попробуйте еще раз:")
            bot.register_next_step_handler(msg, add_enter_code)  # Снова вызываем проверку пароля

    except Exception as e:
        logger.error(f"Ошибка в add_enter_code: {e}", exc_info=True)
        bot.send_message(message.chat.id, "❌ Произошла ошибка. Попробуйте позже.")


def check_auth_code(message, bot, user):
    try:
        if message.text.strip().lower() == '/cancel':
            bot.send_message(message.chat.id, "❌ Действие отменено")
            return

        user_id = message.from_user.id
        user_name = f'{message.from_user.first_name or ""} {message.from_user.last_name or ""}'
        auth_code = message.text.strip()

        # Определяем роль по коду из env
        role = manager.get_role_by_code(auth_code)

        if role:
            # Регистрируем пользователя как сотрудника
            user = User(user_id)


            # Получаем название должности из Enum
            role_display = {
                UserRole.ADMIN: "Админ",
                UserRole.MANAGER: "Председатель",
                UserRole.ACCOUNTANT: "Бухгалтер",
                UserRole.PLUMBER: "Сантехник",
                UserRole.ELECTRIC: "Электрик"
            }
            post_display = role_display.get(role, "Сотрудник")
            user.register_as_staff(role, post_display)

            bot.send_message(message.chat.id, f'Вы успешно авторизованы как {post_display}')
            logger.info(f'Пользователь {message.chat.id} авторизован как {post_display}')

            # Уведомляем админа
            admin_id = manager.get_admin_id()
            if admin_id:
                bot.send_message(admin_id,
                                 f"⚠️ Пользователь {user_id}: {user_name} авторизован как {post_display}")
            return
        else:
            msg = bot.send_message(message.chat.id, "Неверный код авторизации")
            logger.info(f'Пользователь {user_id} ввел неверный код авторизации')
            bot.register_next_step_handler(msg, lambda m: check_auth_code(m, bot, user))

    except Exception as e:
        logger.error(f"Ошибка в enter_auth_code: {e}", exc_info=True)
        bot.send_message(message.chat.id, "❌ Произошла ошибка. Попробуйте позже.")