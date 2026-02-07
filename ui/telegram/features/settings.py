from telebot import types

from services.SecurityManager import SecurityManager
from utils.logger import logger
from model.User import User

manager = SecurityManager()


def settings_apartment(call, bot):
    """Обработка кнопки изменения квартиры"""
    try:
        telegram_id = int(call.data.split('_')[2])
        if call.from_user.id != telegram_id:
            bot.answer_callback_query(call.id, "❌ Недостаточно прав", show_alert=True)
            return

        bot.answer_callback_query(call.id)
        msg = bot.send_message(call.message.chat.id, "Введите новый номер квартиры (1-150):")
        bot.register_next_step_handler(msg, lambda m: process_new_apartment(m, bot, telegram_id))

    except Exception as e:
        logger.error(f"Ошибка в edit_apartment: {e}", exc_info=True)
        bot.answer_callback_query(call.id, "❌ Произошла ошибка. Попробуйте позже.", show_alert=True)


def process_new_apartment(message, bot, telegram_id):
    """Обработка нового номера квартиры"""
    try:
        if message.text.strip().lower() == '/cancel':
            bot.send_message(message.chat.id, "❌ Действие отменено")
            return

        try:
            apartment = int(message.text)
            if 1 <= apartment <= 150:
                User(telegram_id).get_data_from_db().register_in_apartment(apartment)
                bot.send_message(message.chat.id, "✅ Номер квартиры изменен")
            else:
                msg = bot.send_message(message.chat.id, "❌ Номер должен быть от 1 до 150")
                bot.register_next_step_handler(msg, lambda m: process_new_apartment(m, bot, telegram_id))
        except Exception:
            msg = bot.send_message(message.chat.id, "❌ Введите число")
            bot.register_next_step_handler(msg, lambda m: process_new_apartment(m, bot, telegram_id))

    except Exception as e:
        logger.error(f"Ошибка в process_new_apartment: {e}", exc_info=True)
        bot.send_message(message.chat.id, "❌ Произошла ошибка. Попробуйте позже.")


def settings_water(call, bot):
    try:
        telegram_id = int(call.data.split('_')[2])
        if call.from_user.id != telegram_id:
            bot.answer_callback_query(call.id, "❌ Недостаточно прав", show_alert=True)
            return

        bot.answer_callback_query(call.id)
        msg = bot.send_message(
            call.message.chat.id,
            "Введите новое количество счетчиков холодной воды (1-3):\n"
        )
        bot.register_next_step_handler(msg, lambda m: process_new_water(m, bot, telegram_id))

    except Exception as e:
        logger.error(f"Ошибка в edit_water: {e}", exc_info=True)
        bot.answer_callback_query(call.id, "❌ Произошла ошибка. Попробуйте позже.", show_alert=True)


def process_new_water(message, bot, telegram_id):
    try:
        if message.text.strip().lower() == '/cancel':
            bot.send_message(message.chat.id, "❌ Действие отменено")
            return

        try:
            water_count = int(message.text)
            if 1 <= water_count <= 3:
                User(telegram_id).change_water(water_count)
                bot.send_message(message.chat.id, f"✅ Количество счетчиков воды изменено")
            else:
                msg = bot.send_message(message.chat.id, "❌ Введите число от 1 до 3")
                bot.register_next_step_handler(msg, lambda m: process_new_water(m, bot, telegram_id))
        except ValueError:
            msg = bot.send_message(message.chat.id, "❌ Введите число от 1 до 3")
            bot.register_next_step_handler(msg, lambda m: process_new_water(m, bot, telegram_id))

    except Exception as e:
        logger.error(f"Ошибка в process_new_water: {e}", exc_info=True)
        bot.send_message(message.chat.id, "❌ Произошла ошибка. Попробуйте позже.")


def settings_electricity(call, bot):
    try:
        telegram_id = int(call.data.split('_')[2])
        if call.from_user.id != telegram_id:
            bot.answer_callback_query(call.id, "❌ Недостаточно прав", show_alert=True)
            return

        markup = types.InlineKeyboardMarkup()
        markup.row(
            types.InlineKeyboardButton('Однотарифный', callback_data=f'confirm_elec_1_{telegram_id}'),
            types.InlineKeyboardButton('Двухтарифный', callback_data=f'confirm_elec_2_{telegram_id}')
        )

        bot.answer_callback_query(call.id)
        bot.send_message(
            call.message.chat.id,
            "Выберите тип счетчика электричества:",
            reply_markup=markup
        )

    except Exception as e:
        logger.error(f"Ошибка в edit_electric: {e}", exc_info=True)
        bot.answer_callback_query(call.id, "❌ Произошла ошибка. Попробуйте позже.", show_alert=True)


def settings_confirm_electric(call, bot):
    try:
        parts = call.data.split('_')
        elec_type = int(parts[2])
        telegram_id = int(parts[3])

        if call.from_user.id != telegram_id:
            bot.answer_callback_query(call.id, "❌ Недостаточно прав", show_alert=True)
            return

        try:
            User(telegram_id).change_electricity(elec_type)
            bot.answer_callback_query(call.id)
            bot.send_message(
                call.message.chat.id,
                f"✅ Тип электросчетчика изменен на {'однотарифный' if elec_type == 1 else 'двухтарифный'}"
            )
        except Exception as e:
            logger.error(f"Ошибка при изменении электросчетчика: {e}")
            bot.answer_callback_query(call.id, "❌ Ошибка при изменении", show_alert=True)

    except Exception as e:
        logger.error(f"Ошибка в confirm_electric: {e}", exc_info=True)
        bot.answer_callback_query(call.id, "❌ Произошла ошибка. Попробуйте позже.", show_alert=True)


def settings_delete(call, bot):
    try:
        telegram_id = int(call.data.split('_')[2])
        if call.from_user.id != telegram_id:
            bot.answer_callback_query(call.id, "❌ Недостаточно прав", show_alert=True)
            return

        # Создаем клавиатуру подтверждения
        markup = types.InlineKeyboardMarkup()
        markup.row(
            types.InlineKeyboardButton("✅ Да, удалить", callback_data=f'confirm_delete_{telegram_id}'),
            types.InlineKeyboardButton("❌ Нет, отменить", callback_data=f'cancel_delete_{telegram_id}')
        )

        bot.answer_callback_query(call.id)
        bot.send_message(
            call.message.chat.id,
            "⚠️ Вы уверены, что хотите удалить свой аккаунт?\n"
            "Все ваши данные будут безвозвратно удалены!",
            reply_markup=markup
        )

    except Exception as e:
        logger.error(f"Ошибка в delete_account_confirmation: {e}", exc_info=True)
        bot.answer_callback_query(call.id, "❌ Произошла ошибка. Попробуйте позже.", show_alert=True)


def settings_confirm_delete(call, bot):
    try:
        telegram_id = int(call.data.split('_')[2])
        if call.from_user.id != telegram_id:
            bot.answer_callback_query(call.id, "❌ Недостаточно прав", show_alert=True)
            return

        try:
            # Удаляем из всех таблиц
            User(telegram_id).get_data_from_db().delete_all_data()

            bot.answer_callback_query(call.id, "✅ Аккаунт удален", show_alert=True)
            bot.send_message(
                call.message.chat.id,
                "❌ Ваш аккаунт был удален. Для новой регистрации нажмите /start"
            )
            admin_id = manager.get_admin_id()
            bot.send_message(admin_id, f"Пользователь {telegram_id} удалил аккаунт")
            logger.info(f"Пользователь {telegram_id} удалил аккаунт")

        except Exception as e:
            logger.error(f"Ошибка при удалении аккаунта {telegram_id}: {e}")
            bot.answer_callback_query(call.id, "❌ Ошибка при удалении", show_alert=True)

    except Exception as e:
        logger.error(f"Ошибка в  delete_account: {e}", exc_info=True)
        bot.answer_callback_query(call.id, "❌ Произошла ошибка. Попробуйте позже.", show_alert=True)
