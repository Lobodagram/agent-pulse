# Сборка и релиз

[English — команды и полный pipeline](BUILDING.md)

Для разработки Python 3.11+, в CI 3.12. Сборщик использует стандартную библиотеку. PyInstaller — только сборочная зависимость из `requirements-build.txt`; ставьте её в отдельное venv, не глобально. Клиенты устанавливаются/авторизуются отдельно.

## macOS

macOS 14+ и Xcode Command Line Tools. Исходная сборка ищет `python3` в PATH. Для распространяемой сборки сначала упакуйте сборщик:

```sh
python3 -m venv .build/venv
.build/venv/bin/python -m pip install -r requirements-build.txt
.build/venv/bin/python -m unittest discover -s tests -v
.build/venv/bin/python -m PyInstaller --clean --noconfirm --onefile --name pulse-collector --distpath .build collector.py
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

Перетаскивание, смешанный DPI/fullscreen и живые подключения на Windows требуют ручной проверки устройства. Трея пока нет, виджет закрывается штатной кнопкой.

## GitHub Actions

`Checks` — тесты Linux/macOS/Windows и демо UI. `Release packages` — macOS ARM64/Intel, Windows x64, проверка упакованных файлов, zip и SHA256SUMS для тега. Публикуется **предварительный релиз**; право записи имеет только финальная задача публикации. Ключи пользователей и их телеметрия в CI не нужны.

`scripts/public_export.py НОВАЯ_ПАПКА` создаёт отдельное дерево по allowlist без личной истории git/данных и сканирует текст на личные пути и ключи. Приватные контекст/QA не экспортируются. Все публичные изображения — только вымышленное демо.

В 0.3.0 требуется Python 3.11+ (релизная сборка 3.12). Для Windows отдельно соберите консольный сборщик `python -m PyInstaller --clean --noconfirm --onefile --console --name pulse-collector collector.py` и держите pulse-collector.exe рядом с GUI. Хуки и MCP используют консольный сборщик: GUI без консоли не подходит для stdio. В Mac исходники могут выбирать Python через AGENT_PULSE_PYTHON; релиз содержит встроенную среду.

Для локальной разработки Mac: `script/build_and_run.sh` собирает отдельный local-run пакет и не закрывает установленный виджет. Режимы `--verify`, `--debug`, `--logs`, `--telemetry`; для исходников без встроенной среды задайте `AGENT_PULSE_PYTHON` на Python 3.11+. Пути демо/снимков разрешаются от репозитория. Релизные пакеты собираются через `build.sh` со встроенным Python.
