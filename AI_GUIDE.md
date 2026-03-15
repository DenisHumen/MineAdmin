# AI Guide — MineAdmin

Этот файл описывает архитектуру и функционал проекта для удобного изучения нейронными сетями.

## Что это

Веб-приложение для управления Minecraft серверами. Python backend (FastAPI) + JS frontend (SPA). Один `main.py` запускает всё.

## Архитектура

```
main.py → проверка зависимостей → app/webapp.py → FastAPI app
                                    ├── routes/auth.py      (JWT авторизация)
                                    ├── routes/servers.py   (CRUD серверов + запуск)
                                    ├── routes/files.py     (файловый менеджер)
                                    ├── routes/terminal.py  (WebSocket терминал)
                                    ├── routes/config_routes.py (настройки + БД)
                                    └── routes/monitoring.py (системный мониторинг)
```

## Реализованный функционал

### Backend (Python)

| Файл | Что делает | Ключевые функции |
|------|-----------|------------------|
| `main.py` | Точка входа. Проверяет Python версию, pip пакеты, создаёт директории, показывает баннер с IP:port | `check_dependencies()`, `print_banner()` |
| `app/config.py` | Конфиг из `data/config.json`. Пути, SQLite/MySQL URL | `load_config()`, `save_config()` |
| `app/models.py` | SQLAlchemy модели: `User`, `Server`, `AppSettings` | Все поля серверов и пользователей |
| `app/database.py` | Async SQLAlchemy engine. Init, export/import данных между SQLite↔MySQL | `init_db()`, `export_data()`, `import_data()` |
| `app/server_manager.py` | Запуск Minecraft серверов через subprocess. Чтение stdout, отправка stdin, WebSocket broadcast | `start_server()`, `stop_server()`, `send_command()`, `subscribe_output()` |
| `app/downloader.py` | Скачивание серверных JAR из официальных API (Mojang, PaperMC, Purpur, Fabric, Forge) | `download_server()`, `get_available_versions()`, `DownloadProgress` |
| `app/java_manager.py` | Поиск установленных Java, определение нужной версии для MC версии | `find_java_installations()`, `find_suitable_java()`, `get_required_java_version()` |
| `app/network_checker.py` | Локальный/публичный IP, проверка портов, MC server ping | `full_network_check()`, `get_local_ip()` |
| `app/system_monitor.py` | psutil обёртки: CPU, RAM, диск, процессы | `get_system_stats()`, `get_process_stats()`, `format_bytes()` |
| `app/file_manager.py` | Безопасные файловые операции с path traversal защитой | `list_directory()`, `read_text_file()`, `save_text_file()` |
| `app/webapp.py` | Создание FastAPI app, подключение роутеров, SPA fallback | `create_app()` |

### Routes (API)

| Route | Метод | Описание |
|-------|-------|----------|
| `/api/auth/setup` | POST | Создание первого admin пользователя |
| `/api/auth/login` | POST | Авторизация, возвращает JWT |
| `/api/auth/check` | GET | Проверка токена |
| `/api/servers` | GET | Список серверов со статусами |
| `/api/servers` | POST | Создание + фоновая загрузка JAR |
| `/api/servers/{id}/start` | POST | Запуск сервера (auto Java select) |
| `/api/servers/{id}/stop` | POST | Graceful stop (send "stop" → wait → SIGTERM → SIGKILL) |
| `/api/servers/{id}/command` | POST | Отправка команды в stdin |
| `/api/servers/{id}/properties` | GET/PUT | Чтение/запись server.properties |
| `/api/servers/{id}/files` | GET | Список файлов директории |
| `/api/servers/{id}/files/upload` | POST | multipart upload |
| `/api/servers/{id}/files/download` | GET | Скачивание файла |
| `/api/servers/{id}/network` | GET | Проверка LAN/WAN доступности |
| `/ws/terminal/{id}` | WS | Realtime output + command input |
| `/api/monitoring/stats` | GET | CPU/RAM/Disk/Network |
| `/api/config` | GET/PUT | Конфигурация приложения |
| `/api/config/switch-db` | POST | Переключение SQLite↔MySQL с миграцией |

### Frontend (JavaScript SPA)

| Компонент | Описание |
|-----------|----------|
| `App` | Роутинг, авторизация, polling статистики |
| `Pages` | Рендер страниц: dashboard, servers, create, monitoring, settings, docs |
| `ServerCard` | Карточка сервера со статусом и действиями |
| `ServerActions` | Запуск/стоп/терминал/файлы/настройки/сеть/удаление |
| `Terminal` | WebSocket терминал с autocomplete (Tab), историей (↑↓) |
| `FileManager` | Навигация по файлам, редактор, drag&drop upload |
| `Modal` | Универсальные модальные окна |
| `Toast` | Уведомления (success/error/warning/info) |

### CSS

Dark theme с фиолетовым акцентом. Анимации: fadeIn, slideIn, scaleIn, shimmer (progress bar), pulse (статус), glow.
Кастомные компоненты: select с поиском, toggle, progress bar, badge, terminal.
Responsive: sidebar скрывается на мобильных.

## Ключевые паттерны

1. **Async everywhere**: FastAPI async routes, aiohttp для скачивания, aiosqlite/aiomysql
2. **Subprocess management**: Minecraft серверы запускаются через `subprocess.Popen` с отдельным thread для чтения stdout
3. **WebSocket broadcast**: Output серверов транслируется через asyncio.Queue всем подключённым WS клиентам
4. **Progress tracking**: `DownloadProgress` объект обновляется во время скачивания, клиент поллит `/install-progress/{task_id}`
5. **Path traversal protection**: Все файловые операции проверяют что resolved path начинается с server_dir
6. **DB migration**: При переключении SQLite↔MySQL данные экспортируются из текущей БД и импортируются в новую
7. **Auto Java selection**: По MC версии определяется нужная Java, ищется в системе
8. **Auto port assignment**: При создании сервера порт = base_port + N (если порт занят)

## Как расширять

- **Новое ядро**: добавить в `downloader.py` — функция `download_xxx()` + запись в `CORE_TYPES` и маппинг в `download_server()`
- **Новый API endpoint**: создать route в `app/routes/`, подключить в `webapp.py`
- **Новая страница**: добавить в `Pages` объект в `app.js`, добавить nav-item в `showMain()`
- **Новая модель БД**: добавить в `models.py`, при следующем запуске таблица создастся автоматически

## Зависимости

```
fastapi, uvicorn — веб сервер
sqlalchemy, aiosqlite, aiomysql — база данных
aiohttp — HTTP клиент для скачивания
psutil — системный мониторинг
bcrypt, pyjwt — авторизация
python-multipart — file upload
websockets — терминал
jinja2 — HTML шаблоны
aiofiles — async файловые операции
```

## Версия

Хранится в файле `VERSION` в корне проекта. Читается при запуске в `main.py`.
