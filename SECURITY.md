# Security / Безопасность

Do not post credentials, actual account screenshots, session files, counters identifying private work, personal paths or corporate data in issues. Use synthetic fixtures. Report vulnerabilities privately using the contact channels on [the owner's profile](https://github.com/Lobodagram), or GitHub private vulnerability reporting if enabled for this repository.

0.2.x is a preview. Unavailable sources must stay unavailable; no credential scraping, native database inspection, unsafe RPC fallback, model/session invocation or automatic remote plugin installation is an acceptable workaround. Only the fixed native read-only method allowlist may be used. Keep network destinations explicit and bounded, reject redirects, sanitize imports and protect local state against symlinks. Do not execute imported plugin code.

Release packages are unsigned on Windows and ad-hoc signed, not notarized, on macOS. CI produces SHA256 checksums for package comparison, not proof of publisher identity. Build from reviewed source when you need stronger assurance.

Не публикуйте ключи, реальные скриншоты аккаунтов, переписку, личные пути или корпоративные данные. Используйте вымышленные примеры. Уязвимости сообщайте приватно через публичные контакты владельца или GitHub private reporting, если включён.

Недоступность не оправдывает чтение секретов/баз клиентов, вызовы моделей или установку удалённых плагинов. Соблюдайте allowlist методов, фиксированные адреса, запрет redirects и ограничение размера. Предварительные сборки не имеют Windows-подписи/нотариализации Apple. SHA256 проверяет соответствие файлов, но не удостоверяет автора.
