#!/bin/bash
# Подтянуть аддоны с GitHub: git pull --ff-only в каждом репозитории.
# Репозиторий с незакоммиченными правками или разошедшийся с origin не трогается —
# только запись в лог, чтобы автоматический pull никогда не ломал рабочую копию.
#
# Использование: sync.sh <repo_dir> [<repo_dir> ...]
# Запускается вручную или из launchd (ставит setup_mac.sh).

set -u
status=0

for repo in "$@"; do
    name=$(basename "$repo")
    if [ ! -d "$repo/.git" ]; then
        echo "$(date '+%F %T') $name: not a git repository, skipped"
        status=1
        continue
    fi
    if [ -n "$(git -C "$repo" status --porcelain --untracked-files=no)" ]; then
        echo "$(date '+%F %T') $name: local changes, skipped"
        continue
    fi
    if ! out=$(git -C "$repo" pull --ff-only --quiet 2>&1); then
        echo "$(date '+%F %T') $name: pull failed: $out"
        status=1
        continue
    fi
    echo "$(date '+%F %T') $name: $(git -C "$repo" log -1 --format='%h %s')"
done

exit $status
