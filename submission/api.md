# API akimai

Базовый адрес локально: `http://localhost:8000`. Публичный стенд закрыт Basic Auth на уровне nginx. Полная машинная схема находится в `openapi.json` и `openapi.yaml`; Swagger доступен на `/docs`.

## Анкета и подбор

| Метод | Назначение |
|---|---|
| `GET /api/health` | Проверка процесса приложения. |
| `POST /api/intake/start` | Создать сессию и получить первый вопрос. |
| `POST /api/intake/{session_id}/message` | Передать `choice_id` или свободный `text`; возвращает следующий вопрос, прогресс и после завершения `feed`. |
| `POST /api/match` | Прямой расчёт ленты по нормализованному профилю. |
| `GET /api/scenarios` | Просмотреть демокаталог. |

## Заявка предпринимателя

`POST /api/applications` принимает `offer_id`, `session_id`, `applicant_name`, `company_name`, `contact_email`, `contact_phone`, `requested_amount`. Ответ — заявка со статусом `submitted` и событием создания. Воркер создаёт событие `under_review` либо `needs_info`.

`GET /api/applications/{id}` возвращает данные заявки, выбранный продукт, текущий статус и `events` — последовательность событий с актором и временем.

`POST /api/applications/{id}/provide-info` принимает `{ "note": "..." }` только для `needs_info`, возвращает заявку в `submitted` и ставит новую первичную проверку.

## Демо-роль кредитного эксперта

`POST /api/demo/login` принимает `username` и `password`; тестовый ответ содержит Bearer-токен. `GET /api/reviewer/applications` и `POST /api/reviewer/applications/{id}/transition` принимают `Authorization: Bearer demo-reviewer-token` локально или `X-Demo-Token: demo-reviewer-token` на опубликованном стенде (там nginx занимает стандартный `Authorization` под Basic Auth).

Разрешённые переходы эксперта: `submitted/under_review → needs_info`, `submitted/under_review → approved`, `submitted/under_review → rejected`, `needs_info → under_review/approved`. Финальные `approved` и `rejected` неизменяемы.

Ошибки: `401` — нет роли эксперта или неверный логин, `404` — неизвестный ресурс, `409` — недоступный переход, `422` — ошибка схемы или недопустимый вариант.
