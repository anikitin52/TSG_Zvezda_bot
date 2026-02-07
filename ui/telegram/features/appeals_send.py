from telebot import types

from utils.logger import logger
from model.Appeal import Appeal
from model.User import User
from services.SecurityManager import SecurityManager

manager = SecurityManager()
active_dialogs = {}


def send_address(message, bot, recipient_info):
    try:
        # Получаем пользователя
        sender_id = message.from_user.id
        text = message.text.strip() if message.text else ""
        user = User(sender_id).get_data_from_db()
        if not user or user.get_apartment() is None:
            bot.send_message(message.chat.id, "❌ Ошибка: данные пользователя не найдены")
            return

        # Создаем обращение и сохраняем в БД
        appeal = Appeal(
            sender_id=sender_id,
            apartment=user.get_apartment(),
            text=text,
            post=recipient_info['recipient']
        )
        appeal_id = appeal.save_to_db()  # Получаем ID обращения

        # Создаем ответ
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton(
                "✍ Ответить",
                callback_data=f'reply_{sender_id}_{message.message_id}_{appeal_id}'
            )
        )
        if message.from_user.username:
            markup.row(
                types.InlineKeyboardButton("👤 Профиль", url=f"tg://user?id={sender_id}"),
                types.InlineKeyboardButton("💬 Написать", url=f"https://t.me/{message.from_user.username}")
            )

        # Отправляем сообщение получателю
        bot.send_message(
            recipient_info['id'],
            f'📨 Обращение от жителя\n'
            f'🏠 Квартира: {user.apartment}\n\n'
            f'_{text}_',
            parse_mode="Markdown",
            reply_markup=markup
        )

        # Отправка копии председателю (если получатель не председатель)
        if recipient_info['id'] != manager.get_staff_id('Председатель'):
            bot.send_message(
                manager.get_staff_id('Председатель'),
                f'📨 Обращение от жителя:\n'
                f'‍💻 Получатель: {recipient_info["recipient"]}\n'
                f'👤 Отправитель: [{user.get_name()}](tg://user?id={sender_id})\n'
                f'🏠 Квартира: {user.apartment}\n\n'
                f'_{text}_',
                parse_mode="Markdown",
            )

    except Exception as e:
        logger.error(f"Ошибка в send_address: {e}", exc_info=True)
        bot.send_message(message.chat.id, "❌ Произошла ошибка. Попробуйте позже.")


def start_staff_reply(call, bot):
    try:
        # Получение данных из запроса
        parts = call.data.split('_')
        if len(parts) < 4:
            bot.answer_callback_query(call.id, "❌ Ошибка: неверный формат запроса")
            return
        user_id = int(parts[1])
        message_id = int(parts[2])
        appeal_id = int(parts[3])

        # Сохраняем данные диалога
        active_dialogs[call.from_user.id] = {
            'user_id': user_id,
            'message_id': message_id,
            'appeal_id': appeal_id
        }
        # Создаем поле для ответа
        bot.send_message(
            call.from_user.id,
            "✍️ Введите ваш ответ:",
            reply_markup=types.ForceReply(selective=True)
        )

    except Exception as e:
        logger.error(f"Ошибка в start_staff_reply: {e}", exc_info=True)
        bot.answer_callback_query(call.id, "❌ Произошла ошибка. Попробуйте позже.", show_alert=True)


def process_staff_reply(message, bot):
    try:
        # Получаем данные
        staff_id = message.from_user.id
        if staff_id not in active_dialogs:
            return
        dialog_data = active_dialogs[staff_id]
        user_id = dialog_data['user_id']
        appeal_id = dialog_data['appeal_id']

        # Получаем ID сотрудников
        MANAGER_ID = manager.get_staff_id('Председатель')
        ACCOUNTANT_ID = manager.get_staff_id('Бухгалтер')
        ELECTRIC_ID = manager.get_staff_id('Электрик')
        PLUMBER_ID = manager.get_staff_id('Сантехник')

        # Определяем должность отвечающего
        if staff_id == MANAGER_ID:
            staff_position = "председателя ТСЖ"
        elif staff_id == ACCOUNTANT_ID:
            staff_position = "бухгалтера"
        elif staff_id == ELECTRIC_ID:
            staff_position = "электрика"
        elif staff_id == PLUMBER_ID:
            staff_position = "сантехника"
        else:
            staff_position = "администрации"

        # Получаем данные по обращению, на которое отвечаем
        appeal = Appeal(None, None, None, None).get_data_from_db(appeal_id)
        appeal.set_answer(message.text)
        appeal.update_in_db()

        markup = types.InlineKeyboardMarkup()
        if message.from_user.username:
            markup.add(types.InlineKeyboardButton('💬 Написать сотруднику', url=f"tg://user?id={staff_id}"))

        # Отправляем ответ пользователю
        bot.send_message(user_id, f"📩 Ответ {staff_position} на ваше обращение:\n\n{message.text}",
                         reply_markup=markup)

        # Отправляем копию председателю (если отвечающий не председатель)
        if staff_id != manager.get_staff_id('Председатель'):
            user = User(user_id).get_data_from_db()
            if user and user.apartment:
                bot.send_message(
                    manager.get_staff_id('Председатель'),
                    f'📩 Ответ {staff_position}:\n'
                    f'‍💻 Получатель: {user.get_sender_name()}\n'
                    f'🏠 Квартира: {user.apartment}\n\n'
                    f'_{message.text}_',
                    parse_mode="Markdown"
                )

        logger.info(f'Ответ {staff_position} на обращение ID {appeal_id}')
        bot.send_message(staff_id, "✅ Ответ отправлен")
        del active_dialogs[staff_id]


    except Exception as e:
        logger.error(f"Ошибка в process_staff_reply: {e}", exc_info=True)
        bot.send_message(message.chat.id, "❌ Произошла ошибка. Попробуйте позже.")
