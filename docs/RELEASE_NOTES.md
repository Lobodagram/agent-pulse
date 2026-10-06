Agent Pulse 0.8.1 — macOS HTTPS quota fix · Квоты GLM на Mac

Fix the packaged Mac collector’s HTTPS root lookup. 0.8.0 could show local ZCode tokens while remote quotas stayed unavailable because the build Python framework CA file was absent. The same frozen collector succeeded using OS-owned certificates. 0.8.1 adds those roots for frozen macOS while keeping certificate and hostname verification required. No TLS bypass; missing/invalid roots fail closed. Windows and source default trust behavior is retained.

Includes 0.8.0’s persistent Limits/Today switch and private opt-in Z.ai five-hour/week quotas. Each user adds their own key in Settings; no key is distributed. No inference/model calls. Configured-key quotas and local ZCode history have distinct coverage. Billing dates stay manual.

Исправлено чтение HTTPS упакованным обработчиком Mac. В 0.8.0 локальные токены могли отображаться, а квоты — отсутствовать из-за пути к сертификатам Python, которого нет на пользовательском Mac. 0.8.1 использует также системные сертификаты с обязательной проверкой HTTPS. Настройки и личный ключ сохраняются при обновлении.

Переключатель «Лимиты / Сегодня», реальные пятичасовые/недельные квоты GLM, локальное хранение личного ключа. Ключ каждого пользователя вводится отдельно в настройках, в GitHub его нет. Вызовов моделей нет. Квоты ключа и локальные токены ZCode не смешиваются.

182 tests, including four HTTPS-trust regressions. Local and hosted package/live checks are separate gates, recorded in docs/QA.md. This is a MIT public preview. Core analytics effectiveness remains 7/10 pending representative accepted tasks; signing, cold first-start and physical platform acceptance remain open.
