#!/bin/bash
# Подключение аддонов к Blender на Mac через git-клоны и симлинки.
#
# Новый Mac (BlenderIJewel приватный, поэтому сначала вход в GitHub):
#   brew install gh && gh auth login && gh auth setup-git
#   git clone https://github.com/vladimirdyskin/BlenderJewelryAddons.git ~/GitHub/BlenderJewelryAddons
#   ~/GitHub/BlenderJewelryAddons/tools/setup_mac.sh
# Не клонировать в ~/Documents, ~/Desktop, ~/Downloads: macOS не пускает туда фоновые
# задачи, и автосинхронизация работать не будет (скрипт её тогда не ставит).
#
# Что делает (повторный запуск безопасен):
#   1. Клонирует BlenderIJewel рядом с этим репозиторием, если его нет
#      (путь можно задать переменной IJEWEL_DIR).
#   2. Для каждой версии Blender >= 5.2 в ~/Library/Application Support/Blender ставит симлинки:
#        extensions/user_default/jewelry_suite -> <этот репозиторий>/jewelry_suite
#        scripts/addons/BlenderIJewel          -> <BlenderIJewel>
#      Настоящие папки не трогает; старый симлинк заменяет; файл (алиас Finder) убирает в .bak.
#   3. Включает аддоны в Blender (из командной строки) и сохраняет настройки.
#      Blender в этот момент лучше закрыть, иначе при выходе он перезапишет настройки своими.
#   4. Ставит launchd-задачу: sync.sh каждые 15 минут, лог в ~/Library/Logs/blender-addons-sync.log.
#
# Опции: --no-enable (без шага 3), --no-launchd (без шага 4).
# Переменные: IJEWEL_DIR — путь к клону BlenderIJewel, BLENDER — путь к Blender.app/Contents/MacOS/Blender.

set -euo pipefail

SUITE_DIR=$(cd "$(dirname "$0")/.." && pwd)
IJEWEL_DIR=${IJEWEL_DIR:-$(dirname "$SUITE_DIR")/BlenderIJewel}
IJEWEL_URL=https://github.com/vladimirdyskin/BlenderIJewel.git
BLENDER_CONFIG="$HOME/Library/Application Support/Blender"
LABEL=com.vladimirdyskin.blender-addons-sync

DO_ENABLE=1
DO_LAUNCHD=1
for arg in "$@"; do
    case "$arg" in
        --no-enable) DO_ENABLE=0 ;;
        --no-launchd) DO_LAUNCHD=0 ;;
        *) echo "Unknown option: $arg" >&2; exit 2 ;;
    esac
done

# --- 1. клоны ---
if [ ! -d "$IJEWEL_DIR/.git" ]; then
    echo "Cloning BlenderIJewel -> $IJEWEL_DIR"
    if ! GIT_TERMINAL_PROMPT=0 git clone --quiet "$IJEWEL_URL" "$IJEWEL_DIR"; then
        echo "Cannot clone the private BlenderIJewel repo. Log in first:" >&2
        echo "  brew install gh && gh auth login && gh auth setup-git" >&2
        exit 1
    fi
fi

# --- 2. симлинки ---
link() {
    local target=$1 path=$2
    mkdir -p "$(dirname "$path")"
    if [ -L "$path" ]; then
        rm "$path"
    elif [ -d "$path" ]; then
        echo "  SKIP $path: real folder exists, remove it manually"
        return
    elif [ -e "$path" ]; then
        mv "$path" "$path.bak-$(date +%Y%m%d%H%M%S)"
        echo "  moved old file aside: $path.bak-*"
    fi
    ln -s "$target" "$path"
    echo "  $path -> $target"
}

versions=()
if [ -d "$BLENDER_CONFIG" ]; then
    for dir in "$BLENDER_CONFIG"/*/; do
        ver=$(basename "$dir")
        major=${ver%%.*}
        minor=${ver#*.}
        case "$major$minor" in *[!0-9]*) continue ;; esac
        if [ "$major" -gt 5 ] || { [ "$major" -eq 5 ] && [ "$minor" -ge 2 ]; }; then
            versions+=("$ver")
        fi
    done
fi
if [ ${#versions[@]} -eq 0 ]; then
    echo "No Blender 5.2+ settings in $BLENDER_CONFIG. Start Blender once, then run this script again." >&2
    exit 1
fi

for ver in "${versions[@]}"; do
    echo "Blender $ver:"
    link "$SUITE_DIR/jewelry_suite" "$BLENDER_CONFIG/$ver/extensions/user_default/jewelry_suite"
    link "$IJEWEL_DIR" "$BLENDER_CONFIG/$ver/scripts/addons/BlenderIJewel"
done

# --- 3. включить аддоны ---
if [ $DO_ENABLE -eq 1 ]; then
    if [ -z "${BLENDER:-}" ]; then
        app=$(mdfind "kMDItemCFBundleIdentifier == 'org.blenderfoundation.blender'" 2>/dev/null | head -1)
        [ -z "$app" ] && [ -d /Applications/Blender.app ] && app=/Applications/Blender.app
        BLENDER=${app:+$app/Contents/MacOS/Blender}
    fi
    if [ -z "${BLENDER:-}" ] || [ ! -x "$BLENDER" ]; then
        echo "Blender not found; enable the add-ons in Preferences manually (or set BLENDER=...)." >&2
    else
        echo "Enabling add-ons with $BLENDER"
        "$BLENDER" --background --python-exit-code 1 --python-expr '
import bpy
bpy.ops.preferences.addon_refresh()
for module in ("bl_ext.user_default.jewelry_suite", "BlenderIJewel"):
    if module not in bpy.context.preferences.addons:
        bpy.ops.preferences.addon_enable(module=module)
    print("ENABLED" if module in bpy.context.preferences.addons else "FAILED", module)
bpy.ops.wm.save_userpref()
' 2>&1 | grep -E "^(ENABLED|FAILED)" || true
    fi
fi

# --- 4. авто-синхронизация ---
protected() {
    case "$1/" in "$HOME/Documents/"*|"$HOME/Desktop/"*|"$HOME/Downloads/"*) return 0 ;; esac
    return 1
}
if [ $DO_LAUNCHD -eq 1 ] && { protected "$SUITE_DIR" || protected "$IJEWEL_DIR"; }; then
    echo "Auto-sync skipped: repositories inside ~/Documents, ~/Desktop or ~/Downloads are not" >&2
    echo "accessible to background jobs on macOS. Clone into ~/GitHub, or run tools/sync.sh by hand." >&2
    DO_LAUNCHD=0
fi
if [ $DO_LAUNCHD -eq 1 ]; then
    plist="$HOME/Library/LaunchAgents/$LABEL.plist"
    mkdir -p "$(dirname "$plist")" "$HOME/Library/Logs"
    cat > "$plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key><string>$LABEL</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>$SUITE_DIR/tools/sync.sh</string>
        <string>$SUITE_DIR</string>
        <string>$IJEWEL_DIR</string>
    </array>
    <key>StartInterval</key><integer>900</integer>
    <key>RunAtLoad</key><true/>
    <key>StandardOutPath</key><string>$HOME/Library/Logs/blender-addons-sync.log</string>
    <key>StandardErrorPath</key><string>$HOME/Library/Logs/blender-addons-sync.log</string>
</dict>
</plist>
PLIST
    launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
    launchctl bootstrap "gui/$(id -u)" "$plist"
    echo "Auto-sync every 15 min: $plist"
fi

echo "Done."
