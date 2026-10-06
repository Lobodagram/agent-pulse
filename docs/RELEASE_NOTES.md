Agent Pulse v0.4.1 — Reliable observer startup / Исправление сбора событий

The observer previously extracted a one-file runtime on every event: 6–7 seconds on the development Mac versus a configured two-second native deadline. Packages now ship a directory runtime; frozen event tests enforce the actual deadline.

Analytics fixes: explicit tool errors override zero exit status; failed/pending/invalid-time calls break sequences; unreported token components stay unknown; matching per-turn reports from multiple sources are counted once, conflicts remain unknown. Lifecycle-only activity differs from receiving tool events.

83 unit tests plus native fixture and packaged event-path checks. Read docs/AUDIT.md before treating this preview as a full agent-work analysis system. Configured hooks are not proof of real collection: start a new native session, review hook trust when required, execute an ordinary task, then check paired calls in Workflows. Inventory does not prove skill-use/non-use. No exact per-tool token costs or guaranteed savings.

Previously available rotating quota bar, optional foreground selection, resizing, Windows compact strip/tray and account-continuous history remain available. MIT for this original-source snapshot; older tags stay unchanged. English/Russian instructions updated.

Наблюдатель раньше распаковывал среду при каждом событии: 6–7 секунд на Mac при штатном тайм-ауте 2 секунды. Теперь среда поставляется отдельной папкой; проверка упакованного хука использует реальный срок.

Исправлены ложные успехи, цепочки через сбои/незавершённые вызовы/неправильное время, неизвестные значения вместо нуля и повторный подсчёт токенов одного хода из разных источников. События сессии отличаются от поступления вызовов.

83 теста, нативные демонстрационные окна и проверка упакованного пути событий. Подробности в docs/AUDIT.ru.md. Для настоящего сбора нужна новая сессия и доверие хуку, если клиент попросит; после обычной задачи проверьте пары в «Сценариях». Перечень скиллов не доказывает их применение; точные токены каждого инструмента и гарантированная экономия не заявляются.

Mac 14+ ARM64/Intel: ad-hoc signed, not notarized. Windows 10/11 x64: unsigned preview. Keep both Windows executables and the pulse-runtime folder together. Python is bundled. Native client activation, physical multi-monitor/Spaces/fullscreen/sleep-wake, Windows DPI and live third-party accounts still require acceptance.

macOS: среда внутри приложения. Windows: не отделяйте исполняемые файлы от папки pulse-runtime. MIT, инструкции на русском/английском. Реальную активацию клиентов и работу на разных экранах/DPI ещё нужно подтвердить.
