#!/usr/bin/env bash
# orq-git.sh - Deterministic Git & worktree helper for the agents-orchest-git workflow (Linux / macOS).
#
# One integration branch per request : orq/<slug>/integration  (worktree <WtRoot>/<repo>/<slug>/_int)
# One branch + git worktree per task : orq/<slug>/<task>        (worktree <WtRoot>/<repo>/<slug>/<task>)
# Checkpoint tag                     : orq/<slug>/base
#
# Every action prints ONE compact JSON line and uses a stable exit code.
# Never force-pushes, never resets, never rebases.
#
# Exit codes:
#   0 OK / EMPTY / NOOP
#   2 BLOCKED          precondition or usage error (nothing changed)
#   3 SCOPE_VIOLATION  changes outside --files or sensitive files (nothing committed)
#   4 CONFLICT         merge conflict or unresolved conflict markers (target branch unchanged)
#   5 ERROR            git / remote error
#
# Actions:
#   init           --slug <s > --base <b> [--link-deps node_modules,.venv] [--copy-files .env,...] [--wt-root <dir>]
#   spawn          --slug <s > --task <id>
#   spawn-conflict --slug <s > --task <fixId> --from-task <conflictedTask>
#   commit         --slug <s > --task <id|integration> --message "<msg>" --files "a.ts,src/b.ts,docs/"
#   integrate      --slug <s > --task <id>
#   status         --slug <s >
#   list
#   finalize       --slug <s > --mode none|push|merge
#   cleanup        --slug <s > (--task <id> | --all) [--force] [--discard]

set -uo pipefail

INT_NAME='integration'
SENSITIVE_RE='(^|/)\.env(\.[^/]*)?$|\.(key|pem|pfx|p12)$|(^|/)id_(rsa|dsa|ecdsa|ed25519)|secret|credential'

ACTION=''
SLUG=''
TASK=''
FROM_TASK=''
BASE=''
MESSAGE=''
FILES=''
REPO="$PWD"
WT_ROOT=''
LINK_DEPS=''
COPY_FILES='.env,.env.local,.env.development,.env.development.local,.env.test'
MODE='none'
ALL=0
FORCE=0
DISCARD=0

# ---------------------------------------------------------------- JSON helpers
json_escape() {
    local s="$1"
    s="${s//\\/\\\\}"
    s="${s//\"/\\\"}"
    s="${s//$'\n'/\\n}"
    s="${s//$'\r'/\\r}"
    s="${s//$'\t'/\\t}"
    printf '"%s"' "$s"
}

json_array() {
    local out='[' first=1 item
    for item in "$@"; do
        [ -z "$item" ] && continue
        if [ "$first" -eq 1 ]; then first=0; else out+=','; fi
        out+="$(json_escape "$item")"
    done
    out+=']'
    printf '%s' "$out"
}

# Build compact JSON from key=raw_json_value pairs
write_json() {
    local code="$1"; shift
    local out='{' first=1 kv k v
    for kv in "$@"; do
        k="${kv%%=*}"
        v="${kv#*=}"
        if [ "$first" -eq 1 ]; then first=0; else out+=','; fi
        out+="$(json_escape "$k"):$v"
    done
    out+='}'
    printf '%s\n' "$out"
    exit "$code"
}

stop_orq() {
    local code="$1" msg="$2"; shift 2
    local name='ERROR'
    case "$code" in
        2) name='BLOCKED' ;;
        3) name='SCOPE_VIOLATION' ;;
        4) name='CONFLICT' ;;
        5) name='ERROR' ;;
    esac
    write_json "$code" \
        "status=$(json_escape "$name")" \
        "action=$(json_escape "${ACTION:-unknown}")" \
        "message=$(json_escape "$msg")" \
        "$@"
}

# ---------------------------------------------------------------- argument parsing
if [ $# -lt 1 ]; then
    stop_orq 2 'Missing action (init|spawn|spawn-conflict|commit|integrate|status|list|finalize|cleanup).'
fi
ACTION="$1"; shift
case "$ACTION" in
    init|spawn|spawn-conflict|commit|integrate|status|list|finalize|cleanup) ;;
    *) stop_orq 2 "Unknown action '$ACTION'." ;;
esac

while [ $# -gt 0 ]; do
    case "$1" in
        --slug|-s|-Slug)               [ $# -lt 2 ] && stop_orq 2 "Missing value for $1"; SLUG="$2"; shift 2 ;;
        --task|-t|-Task)               [ $# -lt 2 ] && stop_orq 2 "Missing value for $1"; TASK="$2"; shift 2 ;;
        --from-task|-FromTask)         [ $# -lt 2 ] && stop_orq 2 "Missing value for $1"; FROM_TASK="$2"; shift 2 ;;
        --base|-b|-Base)               [ $# -lt 2 ] && stop_orq 2 "Missing value for $1"; BASE="$2"; shift 2 ;;
        --message|-m|-Message)         [ $# -lt 2 ] && stop_orq 2 "Missing value for $1"; MESSAGE="$2"; shift 2 ;;
        --files|-f|-Files)             [ $# -lt 2 ] && stop_orq 2 "Missing value for $1"; FILES="$2"; shift 2 ;;
        --repo|-r|-Repo)               [ $# -lt 2 ] && stop_orq 2 "Missing value for $1"; REPO="$2"; shift 2 ;;
        --wt-root|-WtRoot)             [ $# -lt 2 ] && stop_orq 2 "Missing value for $1"; WT_ROOT="$2"; shift 2 ;;
        --link-deps|-LinkDeps)         [ $# -lt 2 ] && stop_orq 2 "Missing value for $1"; LINK_DEPS="$2"; shift 2 ;;
        --copy-files|-CopyFiles)       [ $# -lt 2 ] && stop_orq 2 "Missing value for $1"; COPY_FILES="$2"; shift 2 ;;
        --mode|-Mode)                  [ $# -lt 2 ] && stop_orq 2 "Missing value for $1"; MODE="$2"; shift 2 ;;
        --all|-All)                    ALL=1; shift ;;
        --force|-Force)                FORCE=1; shift ;;
        --discard|-Discard)            DISCARD=1; shift ;;
        *) stop_orq 2 "Unknown option: $1" ;;
    esac
done

case "$MODE" in
    none|push|merge) ;;
    *) stop_orq 2 "Invalid --mode '$MODE' (expected none|push|merge)." ;;
esac

# ---------------------------------------------------------------- git & path helpers
abs_path() {
    local p="$1"
    if [ -d "$p" ]; then
        (cd "$p" && pwd -P)
    else
        local dir base
        dir="$(dirname "$p")"
        base="$(basename "$p")"
        if [ -d "$dir" ]; then
            printf '%s/%s\n' "$(cd "$dir" && pwd -P)" "$base"
        else
            printf '%s\n' "$p"
        fi
    fi
}

GIT_OUT=''
GIT_ERR=''
GIT_MSG=''
GIT_CODE=0

run_git() {
    local dir="$1"; shift
    local err_file
    err_file="$(mktemp)"
    GIT_OUT="$(git -C "$dir" "$@" 2>"$err_file")"
    GIT_CODE=$?
    GIT_ERR="$(cat "$err_file" 2>/dev/null || true)"
    rm -f "$err_file"
    if [ "$GIT_CODE" -ne 0 ]; then
        if [ -n "$GIT_OUT" ] && [ -n "$GIT_ERR" ]; then
            GIT_MSG="$GIT_OUT"$'\n'"$GIT_ERR"
        elif [ -n "$GIT_ERR" ]; then
            GIT_MSG="$GIT_ERR"
        else
            GIT_MSG="$GIT_OUT"
        fi
    else
        GIT_MSG="$GIT_OUT"
    fi
    return "$GIT_CODE"
}

git_val() {
    local dir="$1"; shift
    if ! run_git "$dir" "$@"; then
        stop_orq 5 "git $* failed." "git=$(json_escape "$GIT_MSG")"
    fi
    printf '%s' "$GIT_OUT" | sed -e 's/[[:space:]]*$//'
}

assert_name() {
    local val="$1" label="$2"
    [ -z "$val" ] && stop_orq 2 "Missing --${label}."
    if ! [[ "$val" =~ ^[a-z0-9][a-z0-9._-]{0,47}$ ]]; then
        stop_orq 2 "Invalid --${label} '$val' (lowercase a-z, 0-9, '.', '_', '-'; max 48 chars)."
    fi
}

split_list() {
    local raw="$1" item
    local -a parts=()
    [ -z "$raw" ] && return 0
    raw="${raw//;/,}"
    IFS=',' read -r -a parts <<< "$raw"
    for item in "${parts[@]}"; do
        item="$(printf '%s' "$item" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')"
        [ -n "$item" ] && printf '%s\n' "$item"
    done
}

rel_path() {
    local p="$1"
    p="${p//\\//}"
    p="$(printf '%s' "$p" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//' -e 's|^\./||' -e 's|^/*||')"
    printf '%s' "$p"
}

branch_of() { printf 'orq/%s/%s' "$SLUG" "$1"; }

test_branch() {
    git -C "$ROOT" rev-parse --verify --quiet "refs/heads/$1" >/dev/null 2>&1
}

test_ancestor() {
    git -C "$ROOT" merge-base --is-ancestor "$1" "$2" >/dev/null 2>&1
}

record_path() { printf '%s/orq/%s.meta' "$COMMON_DIR" "$SLUG"; }

REC_BASE=''
REC_BASE_SHA=''
REC_WT_BASE=''
REC_LINK=''
REC_COPY=''
REC_CREATED=''

read_record() {
    local rp k v
    rp="$(record_path)"
    [ ! -f "$rp" ] && stop_orq 2 "Unknown request '$SLUG'. Run init first (or 'list' to see existing requests)."
    REC_BASE=''; REC_BASE_SHA=''; REC_WT_BASE=''; REC_LINK=''; REC_COPY=''; REC_CREATED=''
    while IFS='=' read -r k v || [ -n "$k" ]; do
        v="${v%$'\r'}"
        case "$k" in
            base)    REC_BASE="$v" ;;
            baseSha) REC_BASE_SHA="$v" ;;
            wtBase)  REC_WT_BASE="$v" ;;
            link)    REC_LINK="$v" ;;
            copy)    REC_COPY="$v" ;;
            created) REC_CREATED="$v" ;;
        esac
    done < "$rp"
    [ -z "$REC_BASE" ] || [ -z "$REC_WT_BASE" ] && stop_orq 5 "Corrupted request metadata: $rp"
}

wt_path_of() {
    if [ "$1" = "$INT_NAME" ]; then
        printf '%s/_int' "$REC_WT_BASE"
    else
        printf '%s/%s' "$REC_WT_BASE" "$1"
    fi
}

wt_for_branch() {
    local target="$1" cur='' line
    while IFS= read -r line; do
        line="${line%$'\r'}"
        case "$line" in
            worktree\ *) cur="${line#worktree }" ;;
            branch\ refs/heads/*)
                if [ "${line#branch refs/heads/}" = "$target" ]; then
                    printf '%s' "$cur"
                    return 0
                fi
                ;;
        esac
    done < <(git -C "$ROOT" worktree list --porcelain)
    return 1
}

wt_git_dir() {
    git_val "$1" rev-parse --absolute-git-dir
}

add_extras() {
    local wt="$1" extras_file f d src dst parent
    local -a added=()
    extras_file="$(wt_git_dir "$wt")/orq-extras.txt"
    : > "$extras_file"

    while IFS= read -r f; do
        [ -z "$f" ] && continue
        src="$ROOT/$f"
        dst="$wt/$f"
        if [ -f "$src" ] && [ ! -e "$dst" ]; then
            parent="$(dirname "$dst")"
            mkdir -p "$parent"
            cp "$src" "$dst"
            printf 'copy|%s\n' "$f" >> "$extras_file"
            added+=("copy|$f")
        fi
    done < <(split_list "$REC_COPY")

    while IFS= read -r d; do
        [ -z "$d" ] && continue
        src="$ROOT/$d"
        dst="$wt/$d"
        if [ -d "$src" ] && [ ! -e "$dst" ] && [ ! -L "$dst" ]; then
            parent="$(dirname "$dst")"
            mkdir -p "$parent"
            case "$(uname -s)" in
                MINGW*|MSYS*|CYGWIN*)
                    cmd //c mklink //J "$(cygpath -w "$dst")" "$(cygpath -w "$src")" >/dev/null
                    ;;
                *)
                    ln -s "$src" "$dst"
                    ;;
            esac
            printf 'link|%s\n' "$d" >> "$extras_file"
            added+=("link|$d")
        fi
    done < <(split_list "$REC_LINK")

    if [ ${#added[@]} -gt 0 ]; then
        printf '%s\n' "${added[@]}"
    fi
}

remove_extras() {
    local wt="$1" extras_file kind rel p
    extras_file="$(wt_git_dir "$wt")/orq-extras.txt"
    [ ! -f "$extras_file" ] && return 0
    while IFS='|' read -r kind rel || [ -n "$kind" ]; do
        rel="${rel%$'\r'}"
        [ -z "$rel" ] && continue
        p="$wt/$rel"
        if [ "$kind" = 'link' ]; then
            # Delete ONLY the symlink itself; never follow it into the shared repo target.
            if [ -L "$p" ]; then
                rm -f "$p"
            elif [ -d "$p" ]; then
                # On systems where ln -s created a junction/directory copy (e.g. MSYS), remove only if empty or reparse point.
                rmdir "$p" 2>/dev/null || true
            fi
        elif [ "$kind" = 'copy' ]; then
            [ -f "$p" ] && rm -f "$p"
        fi
    done < "$extras_file"
}

is_excluded_extra() {
    local p="$1" ex norm
    for ex in "${COPY_PATHS[@]+"${COPY_PATHS[@]}"}"; do
        [ -z "$ex" ] && continue
        [ "$p" = "$ex" ] && return 0
    done
    for ex in "${LINK_DIRS[@]+"${LINK_DIRS[@]}"}"; do
        [ -z "$ex" ] && continue
        norm="${ex%/}"
        if [ "$p" = "$norm" ] || [[ "$p" == "$norm/"* ]]; then
            return 0
        fi
    done
    return 1
}

is_allowed_path() {
    local p="$1" a
    local p_lc a_lc
    p_lc="$(printf '%s' "$p" | tr '[:upper:]' '[:lower:]')"
    for a in "${ALLOWED_FILES[@]}"; do
        a_lc="$(printf '%s' "$a" | tr '[:upper:]' '[:lower:]')"
        [ "$a_lc" = "$p_lc" ] && return 0
        if [[ "$a_lc" == */ ]] && [[ "$p_lc" == "$a_lc"* ]]; then
            return 0
        fi
    done
    return 1
}

is_sensitive_path() {
    printf '%s\n' "$1" | grep -Eiq "$SENSITIVE_RE"
}

MERGE_RESULT_SHA=''
safe_merge() {
    local dir="$1" src="$2" msg="$3"; shift 3
    if run_git "$dir" merge --no-ff -m "$msg" "$src"; then
        MERGE_RESULT_SHA="$(git_val "$dir" rev-parse HEAD)" || exit $?
        return 0
    fi
    if git -C "$dir" rev-parse -q --verify MERGE_HEAD >/dev/null 2>&1; then
        local -a conf=()
        local line
        while IFS= read -r line; do
            line="${line%$'\r'}"
            [ -n "$line" ] && conf+=("$line")
        done < <(git -C "$dir" diff --name-only --diff-filter=U)
        git -C "$dir" merge --abort >/dev/null 2>&1 || true
        stop_orq 4 'Merge conflict; merge aborted, target branch unchanged.' \
            "conflicts=$(json_array "${conf[@]+"${conf[@]}"}")" "$@"
    fi
    stop_orq 5 'Merge failed before starting (target unchanged).' "git=$(json_escape "$GIT_MSG")" "$@"
}

# ---------------------------------------------------------------- context
command -v git >/dev/null 2>&1 || stop_orq 2 'git not found in PATH.'
[ ! -d "$REPO" ] && stop_orq 2 "Repository path does not exist: $REPO"
if ! run_git "$REPO" rev-parse --path-format=absolute --git-common-dir; then
    stop_orq 2 "Not a git repository: $REPO" "git=$(json_escape "$GIT_MSG")"
fi
COMMON_DIR="$(abs_path "$(printf '%s' "$GIT_OUT" | sed -e 's/[[:space:]]*$//')")"
ROOT="$(dirname "$COMMON_DIR")"
if [ ! -e "$ROOT/.git" ]; then
    stop_orq 2 "Unsupported repository layout (bare repo or external git dir): $COMMON_DIR"
fi
REPO_NAME="$(basename "$ROOT")"

# ---------------------------------------------------------------- actions
case "$ACTION" in

init)
    assert_name "$SLUG" 'slug'
    if [ -z "$BASE" ]; then
        BASE="$(git_val "$ROOT" branch --show-current)"
    fi
    [ -z "$BASE" ] && stop_orq 2 'Detached HEAD and no --base given.'
    git -C "$ROOT" rev-parse --verify --quiet "$BASE^{commit}" >/dev/null 2>&1 || stop_orq 2 "Base '$BASE' does not exist."

    IB="$(branch_of "$INT_NAME")"
    [ -f "$(record_path)" ] && stop_orq 2 "Request '$SLUG' already exists. Use 'status' to resume it or pick another slug."
    test_branch "$IB" && stop_orq 2 "Branch $IB already exists."
    git -C "$ROOT" rev-parse --verify --quiet "refs/tags/orq/$SLUG/base" >/dev/null 2>&1 && stop_orq 2 "Tag orq/$SLUG/base already exists."

    if [ -z "$WT_ROOT" ]; then
        WT_ROOT="${ORQ_WT_ROOT:-${XDG_STATE_HOME:-$HOME/.local/state}/orq-wt}"
    fi
    mkdir -p "$WT_ROOT"
    WT_ROOT="$(abs_path "$WT_ROOT")"
    REC_WT_BASE="$WT_ROOT/$REPO_NAME/$SLUG"

    while IFS= read -r d; do
        [ -z "$d" ] && continue
        if [[ "$d" == *..* ]] || [[ "$d" == /* ]]; then
            stop_orq 2 "Invalid --link-deps entry '$d' (must be a relative folder inside the repo)."
        fi
    done < <(split_list "$LINK_DEPS")

    BASE_SHA="$(git_val "$ROOT" rev-parse "$BASE^{commit}")"
    INT_WT="$REC_WT_BASE/_int"
    [ -e "$INT_WT" ] && stop_orq 2 "Path already exists: $INT_WT"

    if ! run_git "$ROOT" worktree add -b "$IB" "$INT_WT" "$BASE_SHA"; then
        stop_orq 5 'git worktree add failed.' "git=$(json_escape "$GIT_MSG")"
    fi
    git_val "$ROOT" tag "orq/$SLUG/base" "$BASE_SHA" >/dev/null
    mkdir -p "$COMMON_DIR/orq"
    REC_BASE="$BASE"
    REC_BASE_SHA="$BASE_SHA"
    REC_LINK="$LINK_DEPS"
    REC_COPY="$COPY_FILES"
    REC_CREATED="$(date '+%Y-%m-%dT%H:%M:%S')"
    {
        printf 'slug=%s\n' "$SLUG"
        printf 'base=%s\n' "$REC_BASE"
        printf 'baseSha=%s\n' "$REC_BASE_SHA"
        printf 'wtBase=%s\n' "$REC_WT_BASE"
        printf 'link=%s\n' "$REC_LINK"
        printf 'copy=%s\n' "$REC_COPY"
        printf 'created=%s\n' "$REC_CREATED"
    } > "$(record_path)"

    local_extras=()
    while IFS= read -r line; do
        [ -n "$line" ] && local_extras+=("$line")
    done < <(add_extras "$INT_WT")

    WARN_JSON='null'
    if [ -n "$(git_val "$ROOT" status --porcelain --untracked-files=no)" ]; then
        WARN_JSON="$(json_escape 'Main working copy has uncommitted changes; they are NOT part of this request.')"
    fi

    write_json 0 \
        "status=\"OK\"" \
        "action=\"init\"" \
        "slug=$(json_escape "$SLUG")" \
        "base=$(json_escape "$BASE")" \
        "baseSha=$(json_escape "$BASE_SHA")" \
        "integrationBranch=$(json_escape "$IB")" \
        "integrationWorktree=$(json_escape "$INT_WT")" \
        "extras=$(json_array "${local_extras[@]+"${local_extras[@]}"}")" \
        "warning=$WARN_JSON"
    ;;

spawn)
    assert_name "$SLUG" 'slug'; assert_name "$TASK" 'task'
    [ "$TASK" = "$INT_NAME" ] && stop_orq 2 "'$INT_NAME' is reserved."
    read_record
    IB="$(branch_of "$INT_NAME")"
    TB="$(branch_of "$TASK")"
    WT="$(wt_path_of "$TASK")"
    test_branch "$TB" && stop_orq 2 "Branch $TB already exists. For a retry use a new task id (e.g. '$TASK-r1')."
    [ -e "$WT" ] && stop_orq 2 "Path already exists: $WT"

    if ! run_git "$ROOT" worktree add -b "$TB" "$WT" "$IB"; then
        stop_orq 5 'git worktree add failed.' "git=$(json_escape "$GIT_MSG")"
    fi
    local_extras=()
    while IFS= read -r line; do
        [ -n "$line" ] && local_extras+=("$line")
    done < <(add_extras "$WT")

    write_json 0 \
        "status=\"OK\"" \
        "action=\"spawn\"" \
        "task=$(json_escape "$TASK")" \
        "branch=$(json_escape "$TB")" \
        "worktree=$(json_escape "$WT")" \
        "baseSha=$(json_escape "$(git_val "$WT" rev-parse HEAD)")" \
        "extras=$(json_array "${local_extras[@]+"${local_extras[@]}"}")"
    ;;

spawn-conflict)
    assert_name "$SLUG" 'slug'; assert_name "$TASK" 'task'; assert_name "$FROM_TASK" 'from-task'
    { [ "$TASK" = "$INT_NAME" ] || [ "$FROM_TASK" = "$INT_NAME" ]; } && stop_orq 2 "'$INT_NAME' is reserved."
    read_record
    IB="$(branch_of "$INT_NAME")"
    FB="$(branch_of "$FROM_TASK")"
    TB="$(branch_of "$TASK")"
    WT="$(wt_path_of "$TASK")"
    test_branch "$FB" || stop_orq 2 "Source task branch not found: $FB"
    test_branch "$TB" && stop_orq 2 "Branch $TB already exists."
    [ -e "$WT" ] && stop_orq 2 "Path already exists: $WT"

    AHEAD="$(git_val "$ROOT" rev-list --count "$IB..$FB")"
    [ "$AHEAD" -eq 0 ] && stop_orq 2 "Task branch '$FB' has no unmerged commits ahead of integration."

    if ! run_git "$ROOT" worktree add -b "$TB" "$WT" "$IB"; then
        stop_orq 5 'git worktree add failed.' "git=$(json_escape "$GIT_MSG")"
    fi

    run_git "$WT" merge --no-ff --no-commit "$FB" || true
    IN_MERGE=0
    git -C "$WT" rev-parse -q --verify MERGE_HEAD >/dev/null 2>&1 && IN_MERGE=1
    if [ "$GIT_CODE" -ne 0 ] && [ "$IN_MERGE" -eq 0 ]; then
        git -C "$ROOT" worktree remove --force "$WT" >/dev/null 2>&1 || true
        git -C "$ROOT" branch -D "$TB" >/dev/null 2>&1 || true
        stop_orq 5 'Failed to start conflict-resolution merge.' "git=$(json_escape "$GIT_MSG")"
    fi

    local_extras=()
    while IFS= read -r line; do
        [ -n "$line" ] && local_extras+=("$line")
    done < <(add_extras "$WT")

    CONFS=()
    while IFS= read -r line; do
        line="${line%$'\r'}"; [ -n "$line" ] && CONFS+=("$line")
    done < <(git -C "$WT" diff --name-only --diff-filter=U)

    AUTO_MERGED=()
    while IFS= read -r line; do
        line="${line%$'\r'}"; [ -n "$line" ] && AUTO_MERGED+=("$line")
    done < <(git -C "$WT" diff --name-only --cached)

    write_json 0 \
        "status=\"OK\"" \
        "action=\"spawn-conflict\"" \
        "task=$(json_escape "$TASK")" \
        "branch=$(json_escape "$TB")" \
        "worktree=$(json_escape "$WT")" \
        "fromTask=$(json_escape "$FROM_TASK")" \
        "fromBranch=$(json_escape "$FB")" \
        "conflicts=$(json_array "${CONFS[@]+"${CONFS[@]}"}")" \
        "autoMerged=$(json_array "${AUTO_MERGED[@]+"${AUTO_MERGED[@]}"}")" \
        "extras=$(json_array "${local_extras[@]+"${local_extras[@]}"}")"
    ;;

commit)
    assert_name "$SLUG" 'slug'; assert_name "$TASK" 'task'
    [ -z "$MESSAGE" ] && stop_orq 2 'Missing --message.'
    read_record
    WT="$(wt_path_of "$TASK")"
    [ ! -d "$WT" ] && stop_orq 2 "Worktree not found: $WT"

    ALLOWED_FILES=()
    while IFS= read -r line; do
        [ -n "$line" ] && ALLOWED_FILES+=("$(rel_path "$line")")
    done < <(split_list "$FILES")
    [ ${#ALLOWED_FILES[@]} -eq 0 ] && stop_orq 2 'Missing --files (comma-separated WRITABLE FILES; folders end with /).'

    COPY_PATHS=(); LINK_DIRS=()
    EXTRAS_FILE="$(wt_git_dir "$WT")/orq-extras.txt"
    if [ -f "$EXTRAS_FILE" ]; then
        while IFS='|' read -r kind rel || [ -n "$kind" ]; do
            rel="$(rel_path "${rel%$'\r'}")"
            [ -z "$rel" ] && continue
            if [ "$kind" = 'link' ]; then LINK_DIRS+=("$rel"); else COPY_PATHS+=("$rel"); fi
        done < "$EXTRAS_FILE"
    fi

    IN_MERGE=0
    git -C "$WT" rev-parse -q --verify MERGE_HEAD >/dev/null 2>&1 && IN_MERGE=1

    ALL_PATHS=()
    TO_STAGE=()
    OUTSIDE=()

    # Parse NUL-delimited git status entries cleanly (supports spaces, renames, deletions).
    while IFS= read -r -d '' tok; do
        [ ${#tok} -lt 4 ] && continue
        xy="${tok:0:2}"
        p="$(rel_path "${tok:3}")"
        orig=''
        if [ "${xy:0:1}" = 'R' ] || [ "${xy:0:1}" = 'C' ]; then
            IFS= read -r -d '' orig || true
            orig="$(rel_path "$orig")"
        fi
        is_excluded_extra "$p" && continue

        ALL_PATHS+=("$p")
        [ -n "$orig" ] && ALL_PATHS+=("$orig")

        if [ "$IN_MERGE" -eq 0 ]; then
            is_allowed_path "$p" || OUTSIDE+=("$p")
            if [ -n "$orig" ]; then is_allowed_path "$orig" || OUTSIDE+=("$orig"); fi
            TO_STAGE+=("$p")
            [ -n "$orig" ] && TO_STAGE+=("$orig")
        else
            is_unmerged=0
            [[ "$xy" =~ U|DD|AA ]] && is_unmerged=1
            is_dirty_wt=0
            [ "${xy:1:1}" != ' ' ] && is_dirty_wt=1
            if [ "$is_unmerged" -eq 1 ] || [ "$is_dirty_wt" -eq 1 ]; then
                is_allowed_path "$p" || OUTSIDE+=("$p")
                if [ -n "$orig" ]; then is_allowed_path "$orig" || OUTSIDE+=("$orig"); fi
                TO_STAGE+=("$p")
                [ -n "$orig" ] && TO_STAGE+=("$orig")
            fi
        fi
    done < <(git -C "$WT" status --porcelain=v1 -z --untracked-files=all)

    if [ ${#ALL_PATHS[@]} -eq 0 ] && [ "$IN_MERGE" -eq 0 ]; then
        write_json 0 \
            "status=\"EMPTY\"" \
            "action=\"commit\"" \
            "task=$(json_escape "$TASK")" \
            "branch=$(json_escape "$(branch_of "$TASK")")" \
            "message=\"No changes to commit.\""
    fi

    if [ ${#OUTSIDE[@]} -gt 0 ]; then
        stop_orq 3 'Changes outside WRITABLE FILES; nothing committed.' \
            "task=$(json_escape "$TASK")" \
            "outOfScope=$(json_array "${OUTSIDE[@]}")" \
            "changed=$(json_array "${ALL_PATHS[@]+"${ALL_PATHS[@]}"}")"
    fi

    SENSITIVE=()
    for p in "${ALL_PATHS[@]+"${ALL_PATHS[@]}"}"; do
        is_sensitive_path "$p" && SENSITIVE+=("$p")
    done
    if [ ${#SENSITIVE[@]} -gt 0 ]; then
        stop_orq 3 'Sensitive-looking files changed; nothing committed.' \
            "task=$(json_escape "$TASK")" \
            "sensitive=$(json_array "${SENSITIVE[@]}")"
    fi

    if [ "$IN_MERGE" -eq 1 ]; then
        UNRESOLVED_MARKERS=()
        while IFS= read -r -d '' tok; do
            [ ${#tok} -lt 4 ] && continue
            xy="${tok:0:2}"
            p="$(rel_path "${tok:3}")"
            if [ "${xy:0:1}" = 'R' ] || [ "${xy:0:1}" = 'C' ]; then
                IFS= read -r -d '' _ || true
            fi
            is_excluded_extra "$p" && continue
            if [[ "$xy" =~ U|DD|AA ]] && [ -f "$WT/$p" ]; then
                if grep -Eq '^(<<<<<<< |=======\r?$|>>>>>>> )' "$WT/$p"; then
                    UNRESOLVED_MARKERS+=("$p")
                fi
            fi
        done < <(git -C "$WT" status --porcelain=v1 -z --untracked-files=all)

        if [ ${#UNRESOLVED_MARKERS[@]} -gt 0 ]; then
            stop_orq 4 'Conflict markers still present in files; nothing committed.' \
                "task=$(json_escape "$TASK")" \
                "files=$(json_array "${UNRESOLVED_MARKERS[@]}")"
        fi
    fi

    for p in "${TO_STAGE[@]+"${TO_STAGE[@]}"}"; do
        if [ -e "$WT/$p" ]; then
            if ! run_git "$WT" add -- "$p"; then
                stop_orq 5 "git add failed for '$p'." "git=$(json_escape "$GIT_MSG")"
            fi
        else
            if ! run_git "$WT" rm -f --quiet --ignore-unmatch -- "$p"; then
                stop_orq 5 "git rm failed for '$p'." "git=$(json_escape "$GIT_MSG")"
            fi
        fi
    done

    if [ "$IN_MERGE" -eq 1 ]; then
        STILL_UNMERGED=()
        while IFS= read -r line; do
            line="${line%$'\r'}"; [ -n "$line" ] && STILL_UNMERGED+=("$line")
        done < <(git -C "$WT" diff --name-only --diff-filter=U)
        if [ ${#STILL_UNMERGED[@]} -gt 0 ]; then
            stop_orq 4 'Unresolved index entries remain; nothing committed.' \
                "task=$(json_escape "$TASK")" \
                "unresolved=$(json_array "${STILL_UNMERGED[@]}")"
        fi
    fi

    MSG_FILE="$(mktemp)"
    printf '%s' "$MESSAGE" > "$MSG_FILE"
    if ! run_git "$WT" commit -F "$MSG_FILE"; then
        rm -f "$MSG_FILE"
        stop_orq 5 'git commit failed (files remain staged in the worktree).' "git=$(json_escape "$GIT_MSG")"
    fi
    rm -f "$MSG_FILE"

    MERGE_BOOL='false'; [ "$IN_MERGE" -eq 1 ] && MERGE_BOOL='true'
    write_json 0 \
        "status=\"OK\"" \
        "action=\"commit\"" \
        "task=$(json_escape "$TASK")" \
        "branch=$(json_escape "$(branch_of "$TASK")")" \
        "commit=$(json_escape "$(git_val "$WT" rev-parse HEAD)")" \
        "files=$(json_array "${ALL_PATHS[@]+"${ALL_PATHS[@]}"}")" \
        "mergeCommit=$MERGE_BOOL"
    ;;

integrate)
    assert_name "$SLUG" 'slug'; assert_name "$TASK" 'task'
    [ "$TASK" = "$INT_NAME" ] && stop_orq 2 "Cannot integrate '$INT_NAME' into itself."
    read_record
    IB="$(branch_of "$INT_NAME")"
    TB="$(branch_of "$TASK")"
    INT_WT="$(wt_path_of "$INT_NAME")"
    test_branch "$TB" || stop_orq 2 "Branch not found: $TB"

    DIRTY="$(git_val "$INT_WT" status --porcelain --untracked-files=no)"
    if [ -n "$DIRTY" ]; then
        DIRTY_ARR=()
        while IFS= read -r line; do [ -n "$line" ] && DIRTY_ARR+=("$line"); done <<< "$DIRTY"
        stop_orq 2 'Integration worktree has uncommitted tracked changes.' "dirty=$(json_array "${DIRTY_ARR[@]}")"
    fi

    AHEAD="$(git_val "$ROOT" rev-list --count "$IB..$TB")"
    if [ "$AHEAD" -eq 0 ]; then
        write_json 0 "status=\"NOOP\"" "action=\"integrate\"" "task=$(json_escape "$TASK")" "message=\"Nothing to merge.\""
    fi

    STAT="$(git -C "$ROOT" diff --stat "$IB...$TB" | sed -e 's/[[:space:]]*$//')"
    safe_merge "$INT_WT" "$TB" "merge($TASK): $SLUG" "task=$(json_escape "$TASK")" "diffStat=$(json_escape "$STAT")"
    MERGE_SHA="$MERGE_RESULT_SHA"
    write_json 0 \
        "status=\"OK\"" \
        "action=\"integrate\"" \
        "task=$(json_escape "$TASK")" \
        "integrationBranch=$(json_escape "$IB")" \
        "mergeCommit=$(json_escape "$MERGE_SHA")" \
        "commitsMerged=$AHEAD"
    ;;

status)
    assert_name "$SLUG" 'slug'
    read_record
    IB="$(branch_of "$INT_NAME")"
    TASK_OBJS=()
    while IFS= read -r b; do
        b="${b%$'\r'}"
        { [ -z "$b" ] || [ "$b" = "$IB" ]; } && continue
        t="${b#"orq/$SLUG/"}"
        sha="$(git_val "$ROOT" rev-parse --short "$b")"
        merged='false'; test_ancestor "$b" "$IB" && merged='true'
        ahead="$(git_val "$ROOT" rev-list --count "$IB..$b")"
        wt_json='null'
        if wt="$(wt_for_branch "$b")"; then wt_json="$(json_escape "$wt")"; fi
        TASK_OBJS+=("{\"task\":$(json_escape "$t"),\"branch\":$(json_escape "$b"),\"sha\":$(json_escape "$sha"),\"merged\":$merged,\"aheadOfIntegration\":$ahead,\"worktree\":$wt_json}")
    done < <(git -C "$ROOT" for-each-ref --format='%(refname:short)' "refs/heads/orq/$SLUG/")

    INT_JSON='null'
    if test_branch "$IB"; then
        isha="$(git_val "$ROOT" rev-parse --short "$IB")"
        iwt_json='null'
        if iwt="$(wt_for_branch "$IB")"; then iwt_json="$(json_escape "$iwt")"; fi
        csb="$(git_val "$ROOT" rev-list --count "$REC_BASE_SHA..$IB")"
        mib='false'; test_ancestor "$IB" "$REC_BASE" && mib='true'
        INT_JSON="{\"branch\":$(json_escape "$IB"),\"sha\":$(json_escape "$isha"),\"worktree\":$iwt_json,\"commitsSinceBase\":$csb,\"mergedIntoBase\":$mib}"
    fi

    TASKS_ARR='['
    first=1
    for obj in "${TASK_OBJS[@]+"${TASK_OBJS[@]}"}"; do
        if [ "$first" -eq 1 ]; then first=0; else TASKS_ARR+=','; fi
        TASKS_ARR+="$obj"
    done
    TASKS_ARR+=']'

    write_json 0 \
        "status=\"OK\"" \
        "action=\"status\"" \
        "slug=$(json_escape "$SLUG")" \
        "base=$(json_escape "$REC_BASE")" \
        "baseSha=$(json_escape "$REC_BASE_SHA")" \
        "integration=$INT_JSON" \
        "tasks=$TASKS_ARR"
    ;;

list)
    REFS=()
    while IFS= read -r line; do
        line="${line%$'\r'}"; [ -n "$line" ] && REFS+=("$line")
    done < <(git -C "$ROOT" for-each-ref --format='%(refname:short)|%(committerdate:iso8601)' 'refs/heads/orq/')

    REQ_OBJS=()
    for line in "${REFS[@]+"${REFS[@]}"}"; do
        name="${line%%|*}"
        date="${line#*|}"
        if [[ "$name" =~ ^orq/([^/]+)/integration$ ]]; then
            s="${BASH_REMATCH[1]}"
            cnt=0
            for r2 in "${REFS[@]}"; do
                n2="${r2%%|*}"
                if [[ "$n2" == "orq/$s/"* ]] && [ "$n2" != "$name" ]; then
                    cnt=$((cnt + 1))
                fi
            done
            has_rec='false'
            [ -f "$COMMON_DIR/orq/$s.meta" ] && has_rec='true'
            REQ_OBJS+=("{\"slug\":$(json_escape "$s"),\"lastCommit\":$(json_escape "$date"),\"taskBranches\":$cnt,\"hasRecord\":$has_rec}")
        fi
    done

    REQS_ARR='['
    first=1
    for obj in "${REQ_OBJS[@]+"${REQ_OBJS[@]}"}"; do
        if [ "$first" -eq 1 ]; then first=0; else REQS_ARR+=','; fi
        REQS_ARR+="$obj"
    done
    REQS_ARR+=']'

    write_json 0 \
        "status=\"OK\"" \
        "action=\"list\"" \
        "repo=$(json_escape "$ROOT")" \
        "requests=$REQS_ARR"
    ;;

finalize)
    assert_name "$SLUG" 'slug'
    read_record
    IB="$(branch_of "$INT_NAME")"
    test_branch "$IB" || stop_orq 2 "Branch not found: $IB"

    CSB="$(git_val "$ROOT" rev-list --count "$REC_BASE_SHA..$IB")"
    LOG_LINES=()
    while IFS= read -r line; do
        line="${line%$'\r'}"; [ -n "$line" ] && LOG_LINES+=("$line")
    done < <(git -C "$ROOT" log --oneline --first-parent "$REC_BASE_SHA..$IB")

    EXTRA_FIELDS=()
    if [ "$MODE" = 'push' ]; then
        if ! run_git "$ROOT" remote get-url origin; then
            stop_orq 2 'No origin remote configured.'
        fi
        REMOTE_URL="$(printf '%s' "$GIT_OUT" | sed -e 's/[[:space:]]*$//')"
        if ! run_git "$ROOT" push -u origin "$IB"; then
            stop_orq 5 'Push failed (no force-push attempted).' "git=$(json_escape "$GIT_MSG")"
        fi
        EXTRA_FIELDS+=("pushed=true" "remoteUrl=$(json_escape "$REMOTE_URL")")
    elif [ "$MODE" = 'merge' ]; then
        CUR="$(git_val "$ROOT" branch --show-current)"
        [ "$CUR" != "$REC_BASE" ] && stop_orq 2 "Main working copy must be on '$REC_BASE' (currently '$CUR')."
        DIRTY="$(git_val "$ROOT" status --porcelain --untracked-files=no)"
        if [ -n "$DIRTY" ]; then
            DIRTY_ARR=()
            while IFS= read -r line; do [ -n "$line" ] && DIRTY_ARR+=("$line"); done <<< "$DIRTY"
            stop_orq 2 'Main working copy has uncommitted tracked changes.' "dirty=$(json_array "${DIRTY_ARR[@]}")"
        fi
        safe_merge "$ROOT" "$IB" "merge(orq): $SLUG" "integrationBranch=$(json_escape "$IB")"
        MERGE_SHA="$MERGE_RESULT_SHA"
        EXTRA_FIELDS+=("merged=true" "mergeCommit=$(json_escape "$MERGE_SHA")")
    fi

    write_json 0 \
        "status=\"OK\"" \
        "action=\"finalize\"" \
        "slug=$(json_escape "$SLUG")" \
        "integrationBranch=$(json_escape "$IB")" \
        "base=$(json_escape "$REC_BASE")" \
        "mode=$(json_escape "$MODE")" \
        "commitsSinceBase=$CSB" \
        "log=$(json_array "${LOG_LINES[@]+"${LOG_LINES[@]}"}")" \
        "${EXTRA_FIELDS[@]+"${EXTRA_FIELDS[@]}"}"
    ;;

cleanup)
    assert_name "$SLUG" 'slug'
    [ "$ALL" -eq 0 ] && [ -z "$TASK" ] && stop_orq 2 'Use --task <id> or --all.'
    read_record
    IB="$(branch_of "$INT_NAME")"

    TARGETS=()
    if [ "$ALL" -eq 1 ]; then
        while IFS= read -r b; do
            b="${b%$'\r'}"; { [ -z "$b" ] || [ "$b" = "$IB" ]; } && continue
            TARGETS+=("$b")
        done < <(git -C "$ROOT" for-each-ref --format='%(refname:short)' "refs/heads/orq/$SLUG/")
        test_branch "$IB" && TARGETS+=("$IB")
    else
        assert_name "$TASK" 'task'
        TARGETS+=("$(branch_of "$TASK")")
    fi

    REMOVED=()
    KEPT_OBJS=()
    for b in "${TARGETS[@]+"${TARGETS[@]}"}"; do
        if ! test_branch "$b"; then
            KEPT_OBJS+=("{\"branch\":$(json_escape "$b"),\"reason\":\"branch not found\"}")
            continue
        fi
        is_merged=0; merged_into=''; allow_force=0
        if [ "$b" = "$IB" ]; then
            test_ancestor "$b" "$REC_BASE" && is_merged=1
            merged_into="$REC_BASE"
            [ "$DISCARD" -eq 1 ] && allow_force=1
        else
            test_ancestor "$b" "$IB" && is_merged=1
            merged_into="$IB"
            { [ "$FORCE" -eq 1 ] || [ "$DISCARD" -eq 1 ]; } && allow_force=1
        fi
        if [ "$is_merged" -eq 0 ] && [ "$allow_force" -eq 0 ]; then
            KEPT_OBJS+=("{\"branch\":$(json_escape "$b"),\"reason\":$(json_escape "not merged into $merged_into")}")
            continue
        fi
        if wt="$(wt_for_branch "$b")"; then
            remove_extras "$wt"
            wt_args=(worktree remove)
            { [ "$FORCE" -eq 1 ] || [ "$DISCARD" -eq 1 ]; } && wt_args+=(--force)
            wt_args+=("$wt")
            if ! run_git "$ROOT" "${wt_args[@]}"; then
                KEPT_OBJS+=("{\"branch\":$(json_escape "$b"),\"reason\":$(json_escape "worktree not removed: $GIT_MSG")}")
                continue
            fi
        fi
        if ! run_git "$ROOT" branch -D "$b"; then
            KEPT_OBJS+=("{\"branch\":$(json_escape "$b"),\"reason\":$(json_escape "$GIT_MSG")}")
            continue
        fi
        REMOVED+=("$b")
    done

    git -C "$ROOT" worktree prune >/dev/null 2>&1 || true
    CLOSED='false'
    if [ "$ALL" -eq 1 ] && ! test_branch "$IB"; then
        git -C "$ROOT" tag -d "orq/$SLUG/base" >/dev/null 2>&1 || true
        rm -f "$(record_path)"
        if [ -d "$REC_WT_BASE" ]; then rmdir "$REC_WT_BASE" 2>/dev/null || true; fi
        CLOSED='true'
    fi

    KEPT_ARR='['
    first=1
    for obj in "${KEPT_OBJS[@]+"${KEPT_OBJS[@]}"}"; do
        if [ "$first" -eq 1 ]; then first=0; else KEPT_ARR+=','; fi
        KEPT_ARR+="$obj"
    done
    KEPT_ARR+=']'

    write_json 0 \
        "status=\"OK\"" \
        "action=\"cleanup\"" \
        "slug=$(json_escape "$SLUG")" \
        "removed=$(json_array "${REMOVED[@]+"${REMOVED[@]}"}")" \
        "kept=$KEPT_ARR" \
        "requestClosed=$CLOSED"
    ;;
esac
