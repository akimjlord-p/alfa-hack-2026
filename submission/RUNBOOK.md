# Runbook

## Локально

```powershell
docker compose up --build -d
docker compose ps
Invoke-WebRequest http://localhost:8000/api/health
```

Стоп: `docker compose down` (том PostgreSQL сохраняется). Для production используется `docker-compose.server.yml`; приложение слушает только `127.0.0.1:8088`, внешний вход проходит через существующий nginx на сервере.

## Диагностика

```powershell
docker compose logs --tail 100 app
docker compose logs --tail 100 worker
docker compose exec db pg_isready -U credit -d credit_navigator
```

Если Яндекс недоступен, анкета продолжает работать по быстрым ответам и локальному извлечению, а финальное ранжирование переключается на правила. Если воркер остановлен, заявка останется в `submitted`; запустите `docker compose up -d worker`.
