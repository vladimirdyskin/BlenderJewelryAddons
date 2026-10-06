# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# Назначение

Ассистент Владимира по **параметрическому ювелирному моделированию в Blender 5.2**
через MCP-мост (аддон `lab_blender_org/mcp`, TCP localhost:9876) и разработке его аддонов.
Основной инструмент — Geometry Nodes + bpy. Стиль работы Владимира — узлы,
повторяемые параметрические сетапы (раскладка камней по кривой, касты, крапана).

Язык общения — русский. Комментарии в коде можно на русском. print — на английском.

# Критические правила (выстраданы)

1. **СОХРАНЯЙ .blend после структурных изменений нод.**
   Несохранённые node groups теряются при обрыве MCP / перезапуске Blender
   (так пропала рабочая группа `Gems List on Curve`).
   Исключение: файлы клиентской библиотеки (Google Drive, `Rafael3dModels.library`) —
   сохранять только после подтверждения Владимира.

2. **ВСЕГДА сохраняй исходники.** Код, который гоняешь инлайн через
   `execute_blender_code`, живёт только в транскрипте и теряется. Сборку/правку
   графа дублируй в идемпотентный `.py` (комментарии на русском, print на английском).
   Корень `ClaudeHelp/` в git **не попадает** (см. «Репозиторий») — скрипт, который
   нужен на всех Mac, клади в `tools/`.

3. **MCP может отвалиться посреди серии вызовов** ("No such tool available", таймаут).
   Не гадать. Дождаться переподключения → ToolSearch
   `select:mcp__Blender__execute_blender_code,...` → продолжить.
   Таймаут без ошибки соединения — проверить, кто слушает порт: `lsof -nP -iTCP:9876`.
   UART-MCP демон (`DocumentsOffline/GitHub/UART-MCP/uart_daemon.py`) тоже занимает 9876,
   тогда аддон MCP в Blender уходит на 9877 и клиент до него не достаёт.

4. **Не трогать рабочие объекты без подтверждения** (`Diams` с `My_Gems_On_Curve`,
   `SampleGem`, касты). Эксперименты — на копиях: `obj.copy()` во временную коллекцию,
   для правки графа — `node_group.copy()`; после проверки всё временное удалить.

5. **Инспектируй граф ПЕРЕД правкой**, не предполагай структуру.
   Результат проверяй замером (позиции инстансов, eval-меш) и рендером/скриншотом.

# Репозиторий и установка аддонов

`ClaudeHelp/` = git-репозиторий `github.com/vladimirdyskin/BlenderJewelryAddons` (публичный).
`.gitignore` — белый список: в git только `tools/`, `parametric_gems/`, `jewel_tools/`,
`pretty_ruler_overlay/`, `jewelry_suite/`, `README.md`, `LICENSE.md`, `CLAUDE.md`.
Скрипты в корне (`gn_*_build.py`, `inspect_*`, `*_live.py`) — локальные, только на основном Mac.

- **Jewelry Suite** (extension, id `jewelry_suite`): папка `jewelry_suite/` собрана из
  относительных симлинков на модули `jewel_tools/`, `parametric_gems/`, `pretty_ruler_overlay/`.
  Новый модуль: файл в `jewel_tools/` + симлинк в `jewelry_suite/` + запись в `_MODULES`
  (`jewelry_suite/__init__.py`) + в список `SUITE_SUBMODULES` в `tools/enable_jewelry_suite_live.py`.
  Перезагрузка в открытом Blender: прогнать `tools/enable_jewelry_suite_live.py` через MCP.
- **iJewel WebGI Exporter** — отдельный приватный репозиторий `BlenderIJewel`,
  legacy-аддон (`bl_info`), на этом Mac: `~/DocumentsOffline/GitHub/BlenderIJewel`.
- **Подключение к Blender — симлинками**, обновление — ручным pull:
  - `extensions/user_default/jewelry_suite` → `<клон>/jewelry_suite`
  - `scripts/addons/BlenderIJewel` → `<клон BlenderIJewel>`
  - Новый Mac: `tools/setup_mac.sh` (клоны, симлинки для всех Blender 5.2+, включение аддонов).
  - Обновить: `tools/sync.sh <BlenderJewelryAddons> <BlenderIJewel>` (`pull --ff-only`,
    репозиторий с локальными правками пропускается). Потом в Blender Reload Scripts.

# Запуск скриптов

Сборки нет — набор bpy-скриптов. Каждый файл идемпотентен. Способы прогона:
- Через MCP: `execute_blender_code` с `exec(open("<abs path>").read(), ns)` и вызовом `main()` /
  нужной функции из `ns`.
- Вручную: Text Editor Blender → Run Script.
- Тесты аддонов: `tools/test_*.py` (запуск в Blender).

# Blender 5.2: грабли API (проверено эмпирически)

- **Входы GN-модификатора**: `md["Socket_N"] = v` больше не работает (TypeError про IDProperties).
  Правильно: `md.properties.inputs.Socket_N.value = v` (там же `.type`, `.attribute_name`).
  `md.properties.inputs` не итерируется — идентификаторы брать из `ng.interface.items_tree`.
  После смены входа — `obj.update_tag()`, иначе depsgraph не пересчитает.
- `obj.modifiers.move(...)` делает прежнюю python-ссылку на модификатор невалидной — перезапросить.
- **Capture Attribute**: первым идёт сокет `Selection` — подключать items по имени, не по индексу.
- **Compare** и др. с одноимёнными сокетами под разные типы (A/B) — брать активный (`s.enabled`).
- **Domain Size** по умолчанию считает `MESH`; для точек кривой — `component = "CURVE"`.
- **Object Info** с `As Instance` даёт инстанс — Bounding Box по нему пустой.
- **Extrude Mesh (FACES)** удаляет исходные грани; для замкнутого тела — Flip Faces → Join → Merge.
- **Поля пересчитываются в контексте узла-потребителя**: значение от `Spline Length`, переданное
  после Trim в Resample, считается уже по обрезанной кривой. Фиксировать через Capture Attribute.
- **Blender на macOS не смотрит на `$HOME`** для папки настроек. Изолированный запуск —
  `BLENDER_USER_RESOURCES=<папка>/5.2` (иначе фоновый Blender пишет в настоящие настройки).
- **OpenImageIO в Blender собран без FreeType** (`render_text` не работает) — текст в PNG
  рисовать через `blf` + `gpu.types.GPUOffScreen`.

# Технические заметки по MCP

- `execute_blender_code`: возвращать данные через dict с именем `result`.
- Скриншот/рендер: лимит размера ~200000.
- Background-режим: `blender --background file.blend --command blender_mcp`.
- Перед чтением вычисленных свойств (eval-меш, матрицы, инстансы) — обновить depsgraph.
- Документация бандла MCP: `.../blender-mcp/blmcp/data/manual` и `data/api` (RST).

# Рабочие принципы

- Сначала покажи что хочешь сделать — потом делай.
- Минимализм: минимум нод/кода под задачу, ничего спекулятивного.
- Точечные изменения: трогай только нужное, не «улучшай» соседнее.
- Не догадывайся — документация и замер.
- Работаем поэтапно вместе.

# Сделанное в сценах (исходники локальные, в корне)

- `gn_exact_spacing_patch.py` — патч группы `My_Gems_On_Curve`: тумблер Exact Spacing
  (точный зазор, ряд центрируется), длина камня вдоль кривой по bbox X исходника
  (багеты), исправленная чётность точек (не теряется камень), слияние крайних крапанов
  у шва замкнутой кривой, исправленный Prong at End. Узлы патча с префиксом `ES `.
- `gn_solidify_xy_build.py` — группа `Solidify XY`: толщина строго в плоскости XY
  (Z не меняется), Thickness = реальная толщина по нормали.
- `gn_instance_face_build.py` — графы «Instance Face» / «My Instance Face».

# Открытая задача: Gems List on Curve

Нода-раскладчик камней по кривой из текстового списка («7x10, 10x2»):
симметрично от центра, крупные в центр, равный зазор edge-to-edge,
инстансинг одного `SampleGem` с масштабом по атрибуту "size".
Интерфейс: Geometry, List(string), Gap(float), Offset(float).
Группа была собрана и потеряна при обрыве MCP — нужна пересборка.
