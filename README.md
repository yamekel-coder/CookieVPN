# 🍪 CookieVPN Bot

Telegram-бот для продажи VPN с автоматической выдачей через **3x-ui** панель.

## Возможности

- 🛒 Продажа подписок (1 мес / 3 мес / 6 мес / 1 год)
- ⭐ Оплата через **Telegram Stars** (встроенная, без комиссии)
- 💳 Оплата через **ЮKassa** (банковские карты)
- 🔑 Автоматическое создание клиента в x-ui после оплаты
- 📡 Поддержка **VLESS + Reality** и **VMess**
- 📊 Статистика трафика из x-ui
- ⏰ Напоминания об истечении подписки
- 🗑 Автоудаление клиентов при истечении
- 📢 Рассылка всем пользователям (для админа)
- 📖 Инструкции по подключению для всех платформ

---

## Установка

### 1. Требования

- Python 3.11+
- Работающая **3x-ui** панель на сервере
- Telegram Bot Token (от [@BotFather](https://t.me/BotFather))

### 2. Клонирование и установка зависимостей

```bash
cd cookievpn
pip install -r requirements.txt
```

### 3. Настройка .env

```bash
cp .env.example .env
```

Заполни `.env`:

```env
# Обязательно
BOT_TOKEN=токен_от_BotFather
ADMIN_IDS=твой_telegram_id

# x-ui панель
XUI_HOST=https://твой-сервер.com:54321
XUI_USERNAME=admin
XUI_PASSWORD=пароль_от_панели
XUI_INBOUND_ID=1          # ID inbound в x-ui (смотри в панели)

# Домен сервера для ссылок подключения
VPN_DOMAIN=твой-сервер.com
VPN_PORT=443

# Метод оплаты: stars | yookassa | both
PAYMENT_METHOD=stars

# Поддержка
SUPPORT_USERNAME=твой_username
```

### 4. Настройка x-ui

1. Зайди в панель x-ui
2. Создай **Inbound** (VLESS + Reality или VMess)
3. Запомни **ID inbound** (обычно 1) — укажи в `XUI_INBOUND_ID`
4. Убедись что API панели доступен по `XUI_HOST`

### 5. Запуск

```bash
python main.py
```

Или через systemd / screen:

```bash
screen -S cookievpn
python main.py
# Ctrl+A, D — свернуть
```

---

## Настройка оплаты

### Telegram Stars (рекомендуется)

Не требует дополнительной настройки. Просто установи `PAYMENT_METHOD=stars`.
Stars — встроенная валюта Telegram, без комиссии для бота.

### ЮKassa (банковские карты)

1. Зарегистрируйся на [yookassa.ru](https://yookassa.ru)
2. Получи `Shop ID` и `Secret Key`
3. Укажи в `.env`:
   ```
   YOOKASSA_SHOP_ID=123456
   YOOKASSA_SECRET_KEY=test_xxxxx
   PAYMENT_METHOD=yookassa
   ```
4. В настройках ЮKassa подключи **Telegram Payments**

---

## Структура проекта

```
cookievpn/
├── main.py           # Точка входа
├── config.py         # Конфигурация и тарифы
├── database.py       # SQLite база данных
├── xui_client.py     # Клиент для x-ui API
├── keyboards.py      # Клавиатуры Telegram
├── scheduler.py      # Фоновые задачи
├── handlers/
│   ├── start.py      # /start, главное меню
│   ├── subscription.py # Просмотр подписки, инструкции
│   ├── payment.py    # Оплата и выдача VPN
│   ├── config_cmd.py # /config — повторная выдача ссылки
│   └── admin.py      # Админ-панель
├── requirements.txt
└── .env.example
```

---

## Команды бота

| Команда | Описание |
|---------|----------|
| `/start` | Главное меню |
| `/config` | Получить ссылку подключения |
| `/admin` | Панель администратора |

---

## Изменение тарифов

Редактируй `PLANS` в `config.py`:

```python
PLANS = {
    "1month": {
        "label": "1 месяц",
        "days": 30,
        "stars": 150,   # цена в Stars
        "rub": 199,     # цена в рублях
        "emoji": "🍪",
    },
    ...
}
```
