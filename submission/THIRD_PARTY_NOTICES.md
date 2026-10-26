# Сторонние компоненты и источники

| Компонент | Версия | Назначение | Лицензия/условие |
|---|---:|---|---|
| Python | 3.11 | Среда приложения | PSF License |
| FastAPI | 0.115.6 | HTTP API и OpenAPI | MIT |
| Uvicorn | 0.34.0 | ASGI-сервер | BSD-3-Clause |
| SQLAlchemy | 2.0.36 | ORM PostgreSQL | MIT |
| psycopg | 3.2.3 | Драйвер PostgreSQL | LGPL-3.0-only / BSD-style parts, см. пакет |
| httpx | 0.28.1 | Проверка доступности источников | BSD-3-Clause |
| openai Python SDK | 3.37.0 | Официально совместимый клиент Yandex AI Studio | Apache-2.0 |
| email-validator | 2.2.0 | Проверка поля email | MIT |
| PostgreSQL | 16-alpine | Хранение данных | PostgreSQL License; образ Docker |
| Caddy/nginx на сервере | 2.10 / системный nginx | Демо-доступ и reverse proxy | Apache-2.0 / BSD-like |

ИИ-провайдер: Yandex AI Studio, модель по умолчанию `yandexgpt/latest`, вызовы идут по OpenAI-совместимому API с URI `gpt://<folder_id>/yandexgpt/latest`. Ответы ИИ используются ограниченно: извлечение фактов и максимум пятиточечный бонус типа инструмента. Внешние страницы банков из `app/seed.py` — первичные открытые ссылки для проверки, но текущие данные продуктов помечены `unverified`.

Этот список не заменяет юридическую проверку лицензий образов и условий внешних банковских источников перед production.
