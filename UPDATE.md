# Как обновить бота на VDS

## Способ 1 — Через Git (рекомендуется)

На сервере выполни:

```bash
cd /opt/cookievpn
git pull origin main
systemctl restart cookievpn
```

Проверь статус:
```bash
systemctl status cookievpn
journalctl -u cookievpn -f
```

---

## Способ 2 — Вручную через SFTP

1. Загрузи изменённые файлы на сервер в `/opt/cookievpn`
2. Перезапусти бота:
   ```bash
   systemctl restart cookievpn
   ```

---

## Если нужно обновить зависимости

```bash
cd /opt/cookievpn
source venv/bin/activate
pip install -r requirements.txt --upgrade
systemctl restart cookievpn
```

---

## Полезные команды

```bash
# Статус бота
systemctl status cookievpn

# Логи в реальном времени
journalctl -u cookievpn -f

# Перезапуск
systemctl restart cookievpn

# Остановка
systemctl stop cookievpn

# Запуск
systemctl start cookievpn
```
