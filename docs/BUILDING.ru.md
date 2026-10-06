# Сборка и релиз

Установка исходников/headless: в собственной виртуальной среде `python3 -m pip install -e .` предоставляет `agent-pulse` и `agent-pulse-mcp`. В метаданных указано Python 3.11+. При старте collector показывает понятное требование версии. Явный `--debug` печатает только класс исключения, без сообщения; хуки молчаливы и не мешают агенту. Linux поддерживает collector/локальный MCP без виджета; адаптеры клиентов различаются.

[English — команды и полный pipeline](BUILDING.md)

Для разработки Python 3.11+, в CI 3.12. Сборщик использует стандартную библиотеку. PyInstaller — только сборочная зависимость из `requirements-build.txt`; ставьте её в отдельное venv, не глобально. Клиенты устанавливаются/авторизуются отдельно.

## macOS

macOS 14+ и Xcode Command Line Tools. Исходная сборка ищет `python3` в PATH. Для распространяемой сборки сначала упакуйте сборщик:

```sh
python3 -m venv .build/venv
.build/venv/bin/python -m pip install -r requirements-build.txt
.build/venv/bin/python -m unittest discover -s tests -v
.build/venv/bin/python -m PyInstaller --clean --noconfirm --onedir --contents-directory pulse-runtime --name pulse-collector --distpath .build collector.py
./build.sh
open 'dist/Agent Pulse.app'
```

Архитектура берётся с машины сборки. Минимальная ОС 14, подпись ad-hoc; нотариализация Apple не настроена. Для публичных скриншотов используйте `--fixture examples/demo.json --language ru --snapshot ПУТЬ`.

## Windows

Windows 10/11 x64, официальный Python 3.12 с Tk:

```powershell
python -m unittest discover -s tests -v
python windows/agent_pulse.py --fixture examples/demo.json
python windows/agent_pulse.py
```

Для exe создайте venv и выполните PyInstaller-команды из английского руководства. Тестируйте также упакованный exe с `--fixture` и **абсолютным** путём `(Resolve-Path examples/demo.json).Path`, а также `--smoke` (команды в английском руководстве): демо закрывается автоматически и не опрашивает аккаунты.

Перетаскивание, смешанный DPI/fullscreen и живые подключения на Windows требуют ручной проверки устройства. Есть плавающее окно, компактная полоска и системный трей.

## GitHub Actions

`Checks` — тесты Linux/macOS/Windows и демо UI. `Release packages` — macOS ARM64/Intel, Windows x64, проверка упакованных файлов, zip и SHA256SUMS для тега. Публикуется **предварительный релиз**; право записи имеет только финальная задача публикации. Ключи пользователей и их телеметрия в CI не нужны.

`scripts/public_export.py НОВАЯ_ПАПКА` создаёт отдельное дерево по allowlist без личной истории git/данных и сканирует текст на личные пути и ключи. Приватные контекст/QA не экспортируются. Все публичные изображения — только вымышленное демо.

Требуется Python 3.11+ (релизная сборка 3.12). Команды Windows из английской инструкции создают отдельный консольный сборщик в режиме `--onedir`; держите `pulse-collector.exe`, папку `pulse-runtime` и GUI вместе. На Mac сборщик и его среда находятся внутри Resources. Не упаковывайте наблюдатель в `--onefile`: распаковка при каждом событии превышала штатный тайм-аут 2 секунды. Проверка `scripts/frozen_smoke.py ПУТЬ_К_СБОРЩИКУ` ограничивает каждый хук этим сроком. Хуки и MCP используют консольный сборщик; GUI без консоли не подходит для stdio. Исходники Mac могут выбирать Python через AGENT_PULSE_PYTHON; релиз содержит встроенную среду.

Для локальной разработки Mac: `script/build_and_run.sh` собирает отдельный local-run пакет и не закрывает установленный виджет. Режимы `--verify`, `--debug`, `--logs`, `--telemetry`; для исходников без встроенной среды задайте `AGENT_PULSE_PYTHON` на Python 3.11+. Пути демо/снимков разрешаются от репозитория. Релизные пакеты собираются через `build.sh` со встроенным Python.
