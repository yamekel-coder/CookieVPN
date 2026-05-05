#!/bin/bash
# Скрипт деплоя CookieVPN на VDS (Ubuntu/Debian)
# Запускать на сервере: bash deploy.sh

set -e

echo "🍪 Деплой CookieVPN..."

# 1. Обновляем систему и ставим зависимости
apt-get update -q
apt-get install -y python3 python3-pip python3-venv git screen

# 2. Создаём директорию
mkdir -p /opt/cookievpn
cd /opt/cookievpn

# 3. Копируем файлы (если запускается локально через scp — пропустить)
# Файлы уже должны быть скопированы в /opt/cookievpn

# 4. Создаём виртуальное окружение
python3 -m venv venv
source venv/bin/activate

# 5. Устанавливаем зависимости
pip install --upgrade pip -q
pip install -r requirements.txt -q

echo "✅ Зависимости установлены"

# 6. Создаём systemd сервис для автозапуска
cat > /etc/systemd/system/cookievpn.service << 'EOF'
[Unit]
Description=CookieVPN Telegram Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/cookievpn
ExecStart=/opt/cookievpn/venv/bin/python main.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

# 7. Включаем и запускаем сервис
systemctl daemon-reload
systemctl enable cookievpn
systemctl restart cookievpn

echo ""
echo "✅ CookieVPN запущен как systemd сервис!"
echo ""
echo "Полезные команды:"
echo "  systemctl status cookievpn   — статус"
echo "  journalctl -u cookievpn -f   — логи в реальном времени"
echo "  systemctl restart cookievpn  — перезапуск"
echo "  systemctl stop cookievpn     — остановка"
