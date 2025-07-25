### TSG Zvezda Bot
**TSG Zvezda Bot** — это Telegram-бот для автоматического сбора показаний счётчиков воды и электричества от жителей многоквартирного дома.  
Он помогает упростить ввод данных, формирует отчёты и уведомляет пользователей в нужное время.

📲 [Перейти к боту в Telegram](https://t.me/Tsg_zvezda_bot)

## 📌 Основные возможности

- ✅ Регистрация по номеру квартиры
- 💧 Указание количества счётчиков воды и типа электросчётчика
- 📥 Ввод, проверка и редактирование показаний
- 📊 Сохранение данных в SQLite-базу
- 📁 Экспорт отчёта в Excel для бухгалтера
- ⏰ Уведомления о начале и завершении сбора
- 🧾 Отправка обращений председателю, бухгалтеру
- 👨‍🔧 Подача заявок на работу электрика и сантехника
- 👥 Поддержка ролей: житель, админ, председатель, бухгалтер
- 💾 Резервное копирование базы данных

  ## 📖 Команды пользователя

| Команда         | Описание                                                   |
|-----------------|------------------------------------------------------------|
| /start        | Запуск бота. Приветственное сообщение и базовая инструкция |
| /send         | Передача показаний счётчиков воды и электричества          |
| /manager      | Отправка обращения председателю ТСЖ                        |
| /accountant   | Отправка обращения бухгалтеру                              |
| /electric     | Заявка на вызов электрика                                  |
| /plumber      | Заявка на вызов сантехника                                  |
| /account      | Просмотр своего профиля (номер квартиры, статус и др.)     |
| /auth         | Авторизация сотрудника (для доступа к административным функциям) |

## 📦 Зависимости

Проект использует следующие основные библиотеки:

| Библиотека          | Назначение                                                     |
|---------------------|----------------------------------------------------------------|
| pyTelegramBotAPI  | Работа с Telegram Bot API (telebot)                          |
| apscheduler       | Планирование задач по времени (уведомления, бэкапы)            |
| pandas            | Работа с таблицами и генерация Excel-отчётов                  |
| sqlite3           | Встроенная база данных Python (устанавливать не нужно)         |

## 🗃 Структура базы данных

Проект использует SQLite с четырьмя основными таблицами:

---

### 📄 Таблица users

Хранит информацию об обычных пользователях.

| Поле              | Тип        | Описание                        |
|-------------------|------------|----------------------------------|
| id              | INTEGER    | Уникальный идентификатор        |
| telegram_id     | INTEGER      | Telegram ID пользователя        |
| apartment       | INTEGER      | Номер квартиры                  |
| water_count     | INTEGER    | Количество водяных счётчиков    |
| electricity_count | INTEGER  | Количество эл. счётчиков        |

---

### 👥 Таблица staff

Хранит информацию о сотрудниках (админ, бухгалтер и т.д.).

| Поле           | Тип      | Описание                            |
|----------------|----------|--------------------------------------|
| id           | INTEGER  | Уникальный идентификатор            |
| post         | TEXT     | Должность (например, "Бухгалтер")   |
| telegram_id  | INTEGER    | Telegram ID сотрудника              |
| name         | TEXT     | Имя и фамилия                       |
| auth_code    | TEXT     | Код авторизации для входа          |

---

### 📊 Таблица meters_data

Хранит переданные показания счётчиков за месяц.

| Поле                    | Тип      | Описание                                 |
|-------------------------|----------|-------------------------------------------|
| id                    | INTEGER  | Уникальный идентификатор                 |
| telegram_id           | INTEGER    | Telegram ID отправителя                  |
| apartment             | INTEGER     | Номер квартиры                           |
| month                 | VARCHAR    | Месяц                |
| type_water_meter      | INTEGER   | Тип водяных счётчиков                    |
| type_electricity_meter| INTEGER     | Тип эл. счётчиков                        |
| cold_water_1          | INTEGER  | Холодная вода, счётчик 1                 |
| cold_water_2          | INTEGER  | Холодная вода, счётчик 2                 |
| cold_water_3          | INTEGER  | Холодная вода, счётчик 3                 |
| hot_water_1           | INTEGER  | Горячая вода, счётчик 1                  |
| hot_water_2           | INTEGER  | Горячая вода, счётчик 2                  |
| hot_water_3           | INTEGER  | Горячая вода, счётчик 3                  |
| electricity_1         | INTEGER  | Электричество, день                      |
| electricity_2         | INTEGER  | Электричество, ночь                      |

---

### 📬 Таблица appeals

Хранит обращения пользователей к сотрудникам.

| Поле           | Тип      | Описание                                  |
|----------------|----------|--------------------------------------------|
| id           | INTEGER  | Уникальный идентификатор обращения         |
| sender_id    |INTEGER    | Telegram ID отправителя                    |
| apartment    |INTEGER     | Квартира отправителя                       |
| message_text | TEXT     | Текст обращения                            |
| recipient_post | TEXT   | Должность адресата (например, "Бухгалтер") |
| answer_text  | TEXT     | Ответ сотрудника (если есть)               |
| status       | TEXT     | Статус обращения (напр. "open", "closed") |

---


