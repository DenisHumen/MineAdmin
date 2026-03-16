# MineAdmin — Minecraft Server Manager

Веб-инструмент для автоматической установки, настройки и управления Minecraft серверами через браузер.

> [!WARNING]
> Крайне не рекомендую использовать файлы из сборки. Запускать исходный код.

## Возможности

- **Установка в один клик** — выберите ядро (Vanilla, Paper, Purpur, Fabric, Forge, Spigot) и версию, нажмите кнопку
- **Несколько серверов** — запускайте параллельно, порты назначаются автоматически
- **Веб-терминал** — консоль сервера с автодополнением команд
- **Файловый менеджер** — просмотр, редактирование, загрузка/выгрузка файлов
- **Мониторинг** — CPU, RAM, диск, сеть в реальном времени
- **Настройки сервера** — server.properties, JVM аргументы, порты через браузер
- **Проверка сети** — доступность из LAN и интернета
- **База данных** — SQLite по умолчанию, поддержка MySQL с синхронизацией
- **Прогресс-бары** — реальный процент загрузки и установки
- **Документация** — встроенная справка по категориям
- **Docker** — готовый Dockerfile и docker-compose

## Быстрый старт

### Требования

- Python 3.10+
- Java 17+ (для MC 1.17+) или Java 21+ (для MC 1.21+)

### Установка

```bash
# Клонировать проект
git clone <repository-url>
cd web_minecraft_server

# Установить зависимости
pip install -r requirements.txt

# Запустить
python main.py
```

При запуске отображается локальный IP и порт для доступа к веб-интерфейсу.

### Docker

```bash
# Запуск через Docker Compose
docker compose up -d

# Или через Docker
docker build -t mineadmin .
docker run -d -p 8080:8080 -p 25565-25575:25565-25575 -v ./data:/app/data mineadmin
```

Данные хранятся в папке `./data` и сохраняются при перезапуске контейнера.

## Использование

1. Откройте браузер по адресу, показанному в консоли (например `http://192.168.1.100:8080`)
2. Создайте аккаунт администратора при первом запуске
3. Нажмите **"Новый сервер"** → выберите ядро → версию → **"Установить"**
4. После установки нажмите **"Запустить"**
5. Используйте **терминал** для команд, **файлы** для настройки

## Поддерживаемые ядра

| Ядро | Описание | Источник |
|------|----------|----------|
| Vanilla | Официальный сервер Mojang | launchermeta.mojang.com |
| Paper | Высокопроизводительный форк Spigot | api.papermc.io |
| Purpur | Форк Paper с доп. функциями | api.purpurmc.org |
| Fabric | Легковесная платформа модов | meta.fabricmc.net |
| Forge | Популярная платформа модов | files.minecraftforge.net |
| Spigot | Форк CraftBukkit | getbukkit.org |

## Требования Java

| Версия MC | Java |
|-----------|------|
| 1.21+ | 21+ |
| 1.17 — 1.20.4 | 17+ |
| 1.16 | 11+ |
| 1.8 — 1.15 | 8+ |

Java определяется автоматически. Если нужная версия не установлена, инструкция по установке отображается в интерфейсе.

## Структура проекта

```
web_minecraft_server/
├── main.py                 # Точка входа, проверка зависимостей
├── VERSION                 # Версия приложения
├── requirements.txt        # Python зависимости
├── Dockerfile              # Docker образ (Ubuntu 24.04)
├── docker-compose.yml      # Docker Compose конфигурация
├── README.md               # Документация
├── AI_GUIDE.md             # Описание для нейросетей
├── app/
│   ├── webapp.py           # FastAPI приложение, маршрутизация
│   ├── config.py           # Конфигурация, пути
│   ├── database.py         # SQLite/MySQL, экспорт/импорт
│   ├── models.py           # SQLAlchemy модели (User, Server, Settings)
│   ├── server_manager.py   # Запуск/остановка серверов, I/O
│   ├── downloader.py       # Скачивание серверов из API
│   ├── java_manager.py     # Поиск и проверка Java
│   ├── network_checker.py  # Проверка портов и IP
│   ├── system_monitor.py   # CPU, RAM, диск, процессы
│   ├── file_manager.py     # Файловые операции
│   ├── routes/
│   │   ├── auth.py         # Авторизация (JWT + bcrypt)
│   │   ├── servers.py      # CRUD серверов, запуск/остановка
│   │   ├── files.py        # Файловый менеджер API
│   │   ├── terminal.py     # WebSocket терминал
│   │   ├── config_routes.py# Настройки, переключение БД
│   │   └── monitoring.py   # Мониторинг системы
│   ├── static/
│   │   ├── css/style.css   # Стили (dark theme, анимации)
│   │   └── js/app.js       # SPA фронтенд
│   └── templates/
│       └── index.html      # HTML шаблон
└── data/                   # Данные (создаётся автоматически)
    ├── servers/            # Файлы серверов
    ├── db/                 # SQLite база
    └── logs/               # Логи
```

## Конфигурация

Файл `data/config.json` создаётся автоматически. Все настройки доступны через веб-интерфейс.

### База данных

- **SQLite** — по умолчанию, без настройки
- **MySQL** — переключение через Настройки → База данных
- При переключении данные автоматически мигрируют
- При недоступности MySQL автоматический откат к SQLite

## API

Все API доступны по `/api/`:

- `POST /api/auth/setup` — создание первого пользователя
- `POST /api/auth/login` — авторизация
- `GET /api/servers` — список серверов
- `POST /api/servers` — создание сервера
- `POST /api/servers/{id}/start` — запуск
- `POST /api/servers/{id}/stop` — остановка
- `WS /ws/terminal/{id}` — терминал (WebSocket)
- `GET /api/monitoring/stats` — системная статистика
- `GET /api/servers/{id}/files` — файлы сервера

## Технологии

- **Backend**: Python 3.10+, FastAPI, SQLAlchemy, aiohttp
- **Frontend**: Vanilla JS (SPA), CSS3 с анимациями
- **Auth**: JWT + bcrypt
- **DB**: SQLite (aiosqlite) / MySQL (aiomysql)
- **Terminal**: WebSocket
- **Monitoring**: psutil
- **Container**: Docker, Ubuntu 24.04

## Сборка в исполняемый файл

Структура проекта совместима с PyInstaller:

```bash
pip install pyinstaller
pyinstaller --onefile --add-data "app/static:app/static" --add-data "app/templates:app/templates" --add-data "VERSION:." main.py
```

## Лицензия

MIT
