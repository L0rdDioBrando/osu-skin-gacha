# OAuth в osu!gacha v0.5.0

Вход подключён к https://osu-gacha-auth.therealdimedrol.workers.dev.
Обычный пользователь выбирает Bancho и нажимает «Войти через osu!». ID определяется автоматически.

## Для разработчика

Общий Worker обслуживает SkillPush и osu!gacha. Исходник находится в `oauth_worker/src/worker.js` и основан на работающей версии SkillPush v13.1. Не заменяйте его старым desktop-only Worker: он не содержит маршрутов сайта. Не удаляйте binding `GACHA_AUTH` и его хранилище — в нём также находятся данные SkillPush.

Client ID и Client Secret остаются в настройках Cloudflare. Используется фактический рабочий Client ID 68443. Значение 86443 из сообщения не подставлялось поверх работающей конфигурации. `wrangler deploy --keep-vars` сохраняет эти настройки.

- `/desktop/start`: создание входа с SHA-256 challenge.
- `/login` и `/oauth/callback`: официальный Authorization Code Grant; state и cookie привязывают ответ к браузеру.
- `/desktop/poll`: результат доступен только создателю verifier.
- `/session`: проверка сессии osu!gacha и данные пользователя.
- `/logout`: аннулирование только этой сессии, сессия сайта остаётся отдельной.
- `/api/v2/*`: разрешённые запросы к osu! выполняет Worker, включая обновление истёкших токенов.

Desktop получает только непрозрачную сессию osu!gacha. В Windows она защищена DPAPI в `.oauth-session`, привязана к пользователю Windows и не экспортируется. Пароль osu!, Client Secret и токены osu! не попадают в Python или exe. Сессия действует до 30 дней с продлением активности, максимум 90 дней; затем нужен новый вход.

Скоры stable, включая F, нормализуются адаптером. За F награда не выдаётся. Звёзды с модами запрашиваются через `/beatmaps/{id}/attributes`. Bancho опрашивается не чаще раза в 61 секунду, данные кэшируются. Gatari и офлайн используют свои прежние адаптеры.

## Проверка и сборка

На Linux сессия приложения сохраняется в Secret Service через явный backend keyring, без автоматического выбора небезопасных файловых хранилищ. Нужен работающий и разблокированный сервис секретов. В Windows сохранён DPAPI. Инструкция сборки AppImage и проверки на Linux: `docs/LINUX.md`.

`python -m unittest tests.test_gacha_oauth tests.test_gacha_oauth_ui` — клиент и окна на тестовых данных.
В `oauth_worker`: `node --test test/worker.test.mjs` — сервер и совместимость SkillPush.
`python build_windows.py` — готовый Windows-архив (нужны PyInstaller и зависимости приложения).
`python build_release.py` — отдельный архив исходников.

Перед обновлением сохранена копия живого Worker в `oauth_worker/.server-backup/2026-09-20-live.js`. Она не включается в архив программы.
