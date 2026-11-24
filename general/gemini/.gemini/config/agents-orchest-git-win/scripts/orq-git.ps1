<#
.SYNOPSIS
  orq-git.ps1 - Deterministic Git & worktree helper for the agents-orchest-git workflow.

.DESCRIPTION
  One integration branch per request  : orq/<slug>/integration  (worktree <WtRoot>\<repo>\<slug>\_int)
  One branch + git worktree per task  : orq/<slug>/<task>        (worktree <WtRoot>\<repo>\<slug>\<task>)
  Checkpoint tag                      : orq/<slug>/base

  Every action prints ONE compact JSON line and uses a stable exit code, so agents
  spend almost no tokens on Git. Never force-pushes, never resets, never rebases.

  Exit codes:
    0 OK / EMPTY / NOOP
    2 BLOCKED          precondition or usage error (nothing changed)
    3 SCOPE_VIOLATION  changes outside -Files or sensitive files (nothing committed)
    4 CONFLICT         merge conflict or unresolved conflict markers (target branch unchanged)
    5 ERROR            git / remote error

  Actions:
    init           -Slug -Base [-LinkDeps node_modules,.venv] [-CopyFiles .env,...] [-WtRoot C:\wt]
    spawn          -Slug -Task
    spawn-conflict -Slug -Task <fixId> -FromTask <conflictedTask>
    commit         -Slug -Task -Message "<conventional msg>" -Files "a.ts,src/b.ts,docs/"
    integrate      -Slug -Task
    status         -Slug
    list
    finalize       -Slug -Mode none|push|merge
    cleanup        -Slug (-Task <id> | -All) [-Force] [-Discard]

.EXAMPLE
  powershell -NoProfile -ExecutionPolicy Bypass -File orq-git.ps1 init -Repo C:\code\app -Slug login-oauth -Base main -LinkDeps node_modules
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [ValidateSet('init', 'spawn', 'spawn-conflict', 'commit', 'integrate', 'status', 'list', 'finalize', 'cleanup')]
    [string]$Action,
    [string]$Slug,
    [string]$Task,
    [string]$FromTask,
    [string]$Base,
    [string]$Message,
    [string]$Files,
    [string]$Repo = (Get-Location).Path,
    [string]$WtRoot,
    [string]$LinkDeps = '',
    [string]$CopyFiles = '.env,.env.local,.env.development,.env.development.local,.env.test',
    [ValidateSet('none', 'push', 'merge')]
    [string]$Mode = 'none',
    [switch]$All,
    [switch]$Force,
    [switch]$Discard
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0
try { [Console]::OutputEncoding = New-Object System.Text.UTF8Encoding $false } catch { }
$IntName = 'integration'
$SensitiveRegex = '(^|/)\.env(\.[^/]*)?$|\.(key|pem|pfx|p12)$|(^|/)id_(rsa|dsa|ecdsa|ed25519)|secret|credential'

# ---------------------------------------------------------------- output helpers
function Write-Result {
    param([hashtable]$Data, [int]$Code = 0)
    $o = [ordered]@{ status = 'OK'; action = $Action }
    foreach ($k in $Data.Keys) { $o[$k] = $Data[$k] }
    Write-Output ($o | ConvertTo-Json -Depth 8 -Compress)
    exit $Code
}

function Stop-Orq {
    param([int]$Code, [string]$Msg, [hashtable]$Extra = @{})
    $names = @{ 2 = 'BLOCKED'; 3 = 'SCOPE_VIOLATION'; 4 = 'CONFLICT'; 5 = 'ERROR' }
    $d = @{ status = $names[$Code]; message = $Msg }
    foreach ($k in $Extra.Keys) { $d[$k] = $Extra[$k] }
    Write-Result $d $Code
}

# ---------------------------------------------------------------- git helpers
function Invoke-Git {
    param([string]$Dir, [string[]]$GitArgs)
    # stdout and stderr are kept apart so git warnings (e.g. CRLF notices) never corrupt parsed values.
    $prev = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    $errFile = [System.IO.Path]::GetTempFileName()
    try {
        $out = & git -C $Dir @GitArgs 2> $errFile
        $code = $LASTEXITCODE
        $err = [System.IO.File]::ReadAllText($errFile)
    }
    finally {
        $ErrorActionPreference = $prev
        try { if (Test-Path -LiteralPath $errFile) { [System.IO.File]::Delete($errFile) } } catch { }
    }
    $text = (@($out) | ForEach-Object { "$_" }) -join "`n"
    $msg = $text
    if ($code -ne 0) { $msg = ($text + "`n" + $err).Trim() }
    return [pscustomobject]@{ Code = $code; Out = $text; Msg = $msg }
}

function Get-GitValue {
    param([string]$Dir, [string[]]$GitArgs)
    $r = Invoke-Git $Dir $GitArgs
    if ($r.Code -ne 0) { Stop-Orq 5 ("git {0} failed." -f ($GitArgs -join ' ')) @{ git = $r.Msg } }
    return $r.Out.Trim()
}

function Get-Lines {
    param([string]$Text)
    return @($Text -split "`n" | ForEach-Object { $_.Trim() } | Where-Object { $_ })
}

function Assert-Name {
    param([string]$Value, [string]$Label)
    if (-not $Value) { Stop-Orq 2 "Missing -$Label." }
    if ($Value -notmatch '^[a-z0-9][a-z0-9._-]{0,47}$') {
        Stop-Orq 2 "Invalid -$Label '$Value' (lowercase a-z, 0-9, '.', '_', '-'; max 48 chars)."
    }
}

function Split-List {
    param([string]$Value)
    if (-not $Value) { return @() }
    return @($Value -split '[,;]' | ForEach-Object { $_.Trim() } | Where-Object { $_ })
}

function ConvertTo-RelPath {
    param([string]$P)
    return (($P.Trim() -replace '\\', '/') -replace '^\./', '').TrimStart('/')
}

function Get-Branch { param([string]$T) return "orq/$Slug/$T" }

function Test-Branch {
    param([string]$B)
    return ((Invoke-Git $Root @('rev-parse', '--verify', '--quiet', "refs/heads/$B")).Code -eq 0)
}

function Test-Ancestor {
    param([string]$A, [string]$B)
    return ((Invoke-Git $Root @('merge-base', '--is-ancestor', $A, $B)).Code -eq 0)
}

function Get-RecordPath { return (Join-Path (Join-Path $CommonDir 'orq') "$Slug.json") }

function Read-Record {
    $p = Get-RecordPath
    if (-not (Test-Path -LiteralPath $p)) { Stop-Orq 2 "Unknown request '$Slug'. Run init first (or 'list' to see existing requests)." }
    return (Get-Content -LiteralPath $p -Raw | ConvertFrom-Json)
}

function Get-WtPath {
    param($Rec, [string]$T)
    if ($T -eq $IntName) { return (Join-Path $Rec.wtBase '_int') }
    return (Join-Path $Rec.wtBase $T)
}

function Get-WorktreeMap {
    $map = @{}
    $cur = $null
    foreach ($line in (Get-Lines (Get-GitValue $Root @('worktree', 'list', '--porcelain')))) {
        if ($line.StartsWith('worktree ')) { $cur = ($line.Substring(9) -replace '/', '\') }
        elseif ($line.StartsWith('branch refs/heads/') -and $cur) { $map[$line.Substring(18)] = $cur }
    }
    return $map
}

# ---------------------------------------------------------------- worktree extras (.env copies, dependency junctions)
function Get-WtGitDir { param([string]$Wt) return (Get-GitValue $Wt @('rev-parse', '--absolute-git-dir')) }

function Add-Extras {
    param([string]$Wt, $Rec)
    $lines = @()
    foreach ($f in @($Rec.copy | Where-Object { $_ })) {
        $src = Join-Path $Root $f; $dst = Join-Path $Wt $f
        if ((Test-Path -LiteralPath $src -PathType Leaf) -and -not (Test-Path -LiteralPath $dst)) {
            $parent = Split-Path $dst -Parent
            if (-not (Test-Path -LiteralPath $parent)) { New-Item -ItemType Directory -Path $parent -Force | Out-Null }
            Copy-Item -LiteralPath $src -Destination $dst
            $lines += "copy|$f"
        }
    }
    foreach ($d in @($Rec.link | Where-Object { $_ })) {
        $src = Join-Path $Root $d; $dst = Join-Path $Wt $d
        if ((Test-Path -LiteralPath $src -PathType Container) -and -not (Test-Path -LiteralPath $dst)) {
            $parent = Split-Path $dst -Parent
            if (-not (Test-Path -LiteralPath $parent)) { New-Item -ItemType Directory -Path $parent -Force | Out-Null }
            New-Item -ItemType Junction -Path $dst -Target $src | Out-Null
            $lines += "link|$d"
        }
    }
    Set-Content -LiteralPath (Join-Path (Get-WtGitDir $Wt) 'orq-extras.txt') -Value $lines -Encoding ASCII
    return @($lines)
}

function Get-ExtraEntries {
    param([string]$Wt)
    $p = Join-Path (Get-WtGitDir $Wt) 'orq-extras.txt'
    if (-not (Test-Path -LiteralPath $p)) { return @() }
    return @(Get-Content -LiteralPath $p | Where-Object { $_ -match '^(copy|link)\|' })
}

function Remove-Extras {
    param([string]$Wt)
    foreach ($e in (Get-ExtraEntries $Wt)) {
        $kind, $rel = $e -split '\|', 2
        $p = Join-Path $Wt $rel
        if (-not (Test-Path -LiteralPath $p)) { continue }
        if ($kind -eq 'link') {
            $item = Get-Item -LiteralPath $p -Force
            # Delete ONLY the junction itself (non-recursive) so the shared target is never touched.
            if ($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) { [System.IO.Directory]::Delete($p, $false) }
        }
        else { [System.IO.File]::Delete($p) }
    }
}

function Test-ExcludedExtra {
    param([string]$RelPath, [string[]]$CopyPaths, [string[]]$LinkDirs)
    if ($CopyPaths -contains $RelPath) { return $true }
    foreach ($d in $LinkDirs) {
        $norm = $d.TrimEnd('/')
        if ($RelPath -ieq $norm -or $RelPath.StartsWith("$norm/", [System.StringComparison]::OrdinalIgnoreCase)) { return $true }
    }
    return $false
}

function Get-StatusEntries {
    param([string]$Wt, [string[]]$CopyPaths, [string[]]$LinkDirs)
    $r = Invoke-Git $Wt @('status', '--porcelain=v1', '-z', '--untracked-files=all')
    if ($r.Code -ne 0) { Stop-Orq 5 'git status failed.' @{ git = $r.Msg } }
    $entries = New-Object System.Collections.Generic.List[object]
    $tokens = @($r.Out -split [char]0)
    $i = 0
    while ($i -lt $tokens.Count) {
        $e = $tokens[$i]
        $i++
        if (-not $e -or $e.Length -lt 4) { continue }
        $xy = $e.Substring(0, 2)
        $p = ConvertTo-RelPath $e.Substring(3)
        $orig = $null
        if ($xy[0] -eq 'R' -or $xy[0] -eq 'C') {
            if ($i -lt $tokens.Count) { $orig = ConvertTo-RelPath $tokens[$i]; $i++ }
        }
        if (Test-ExcludedExtra $p $CopyPaths $LinkDirs) { continue }
        $entries.Add([pscustomobject]@{ XY = $xy; Path = $p; Orig = $orig })
    }
    return $entries.ToArray()
}

function Test-Allowed {
    param([string]$P, [string[]]$Allowed)
    foreach ($a in $Allowed) {
        if ($a -ieq $P) { return $true }
        if ($a.EndsWith('/') -and $P.StartsWith($a, [System.StringComparison]::OrdinalIgnoreCase)) { return $true }
    }
    return $false
}

function Invoke-SafeMerge {
    # Merges $Source into the branch checked out at $Dir. On failure aborts and stops with exit 4/5.
    param([string]$Dir, [string]$Source, [string]$Msg, [hashtable]$Extra = @{})
    $m = Invoke-Git $Dir @('merge', '--no-ff', '-m', $Msg, $Source)
    if ($m.Code -eq 0) { return (Get-GitValue $Dir @('rev-parse', 'HEAD')) }
    $inMerge = (Invoke-Git $Dir @('rev-parse', '-q', '--verify', 'MERGE_HEAD')).Code -eq 0
    if ($inMerge) {
        $conf = @(Get-Lines (Invoke-Git $Dir @('diff', '--name-only', '--diff-filter=U')).Out)
        Invoke-Git $Dir @('merge', '--abort') | Out-Null
        $Extra['conflicts'] = $conf
        Stop-Orq 4 'Merge conflict; merge aborted, target branch unchanged.' $Extra
    }
    $Extra['git'] = $m.Msg
    Stop-Orq 5 'Merge failed before starting (target unchanged).' $Extra
}

# ---------------------------------------------------------------- context
if (-not (Get-Command git -ErrorAction SilentlyContinue)) { Stop-Orq 2 'git not found in PATH.' }
$rc = Invoke-Git $Repo @('rev-parse', '--path-format=absolute', '--git-common-dir')
if ($rc.Code -ne 0) { Stop-Orq 2 "Not a git repository: $Repo" @{ git = $rc.Msg } }
$CommonDir = (Resolve-Path -LiteralPath $rc.Out.Trim()).Path
$Root = Split-Path $CommonDir -Parent
if (-not (Test-Path -LiteralPath (Join-Path $Root '.git'))) { Stop-Orq 2 "Unsupported repository layout (bare repo or external git dir): $CommonDir" }
$RepoName = Split-Path $Root -Leaf

# ---------------------------------------------------------------- actions
switch ($Action) {

    'init' {
        Assert-Name $Slug 'Slug'
        if (-not $Base) { $Base = (Get-GitValue $Root @('branch', '--show-current')) }
        if (-not $Base) { Stop-Orq 2 'Detached HEAD and no -Base given.' }
        if ((Invoke-Git $Root @('rev-parse', '--verify', '--quiet', "$Base^{commit}")).Code -ne 0) { Stop-Orq 2 "Base '$Base' does not exist." }
        $ib = Get-Branch $IntName
        if (Test-Path -LiteralPath (Get-RecordPath)) { Stop-Orq 2 "Request '$Slug' already exists. Use 'status' to resume it or pick another slug." }
        if (Test-Branch $ib) { Stop-Orq 2 "Branch $ib already exists." }
        if ((Invoke-Git $Root @('rev-parse', '--verify', '--quiet', "refs/tags/orq/$Slug/base")).Code -eq 0) { Stop-Orq 2 "Tag orq/$Slug/base already exists." }

        if (-not $WtRoot) { if ($env:ORQ_WT_ROOT) { $WtRoot = $env:ORQ_WT_ROOT } else { $WtRoot = Join-Path $env:SystemDrive 'wt' } }
        $WtRoot = [System.IO.Path]::GetFullPath($WtRoot)
        $wtBase = Join-Path (Join-Path $WtRoot $RepoName) $Slug
        foreach ($d in (Split-List $LinkDeps)) { if ($d -match '\.\.' -or [System.IO.Path]::IsPathRooted($d)) { Stop-Orq 2 "Invalid -LinkDeps entry '$d' (must be a relative folder inside the repo)." } }

        $baseSha = Get-GitValue $Root @('rev-parse', "$Base^{commit}")
        $rec = [ordered]@{
            slug = $Slug; base = $Base; baseSha = $baseSha; wtBase = $wtBase
            link = @(Split-List $LinkDeps); copy = @(Split-List $CopyFiles); created = (Get-Date).ToString('s')
        }
        $intWt = Join-Path $wtBase '_int'
        if (Test-Path -LiteralPath $intWt) { Stop-Orq 2 "Path already exists: $intWt" }

        $r = Invoke-Git $Root @('worktree', 'add', '-b', $ib, $intWt, $baseSha)
        if ($r.Code -ne 0) { Stop-Orq 5 'git worktree add failed.' @{ git = $r.Msg } }
        Get-GitValue $Root @('tag', "orq/$Slug/base", $baseSha) | Out-Null
        New-Item -ItemType Directory -Force -Path (Join-Path $CommonDir 'orq') | Out-Null
        $rec | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Get-RecordPath) -Encoding UTF8
        $extras = Add-Extras $intWt ([pscustomobject]$rec)

        $warn = $null
        if ((Get-GitValue $Root @('status', '--porcelain', '--untracked-files=no'))) {
            $warn = 'Main working copy has uncommitted changes; they are NOT part of this request.'
        }
        Write-Result @{ slug = $Slug; base = $Base; baseSha = $baseSha; integrationBranch = $ib; integrationWorktree = $intWt; extras = $extras; warning = $warn }
    }

    'spawn' {
        Assert-Name $Slug 'Slug'; Assert-Name $Task 'Task'
        if ($Task -eq $IntName) { Stop-Orq 2 "'$IntName' is reserved." }
        $rec = Read-Record
        $ib = Get-Branch $IntName; $tb = Get-Branch $Task; $wt = Get-WtPath $rec $Task
        if (Test-Branch $tb) { Stop-Orq 2 "Branch $tb already exists. For a retry use a new task id (e.g. '$Task-r1')." }
        if (Test-Path -LiteralPath $wt) { Stop-Orq 2 "Path already exists: $wt" }
        $r = Invoke-Git $Root @('worktree', 'add', '-b', $tb, $wt, $ib)
        if ($r.Code -ne 0) { Stop-Orq 5 'git worktree add failed.' @{ git = $r.Msg } }
        $extras = Add-Extras $wt $rec
        Write-Result @{ task = $Task; branch = $tb; worktree = $wt; baseSha = (Get-GitValue $wt @('rev-parse', 'HEAD')); extras = $extras }
    }

    'spawn-conflict' {
        Assert-Name $Slug 'Slug'; Assert-Name $Task 'Task'; Assert-Name $FromTask 'FromTask'
        if ($Task -eq $IntName -or $FromTask -eq $IntName) { Stop-Orq 2 "'$IntName' is reserved." }
        $rec = Read-Record
        $ib = Get-Branch $IntName; $fb = Get-Branch $FromTask; $tb = Get-Branch $Task; $wt = Get-WtPath $rec $Task
        if (-not (Test-Branch $fb)) { Stop-Orq 2 "Source task branch not found: $fb" }
        if (Test-Branch $tb) { Stop-Orq 2 "Branch $tb already exists." }
        if (Test-Path -LiteralPath $wt) { Stop-Orq 2 "Path already exists: $wt" }
        $ahead = [int](Get-GitValue $Root @('rev-list', '--count', "$ib..$fb"))
        if ($ahead -eq 0) { Stop-Orq 2 "Task branch '$fb' has no unmerged commits ahead of integration." }

        $r = Invoke-Git $Root @('worktree', 'add', '-b', $tb, $wt, $ib)
        if ($r.Code -ne 0) { Stop-Orq 5 'git worktree add failed.' @{ git = $r.Msg } }

        $m = Invoke-Git $wt @('merge', '--no-ff', '--no-commit', $fb)
        $inMerge = (Invoke-Git $wt @('rev-parse', '-q', '--verify', 'MERGE_HEAD')).Code -eq 0
        if ($m.Code -ne 0 -and -not $inMerge) {
            Invoke-Git $Root @('worktree', 'remove', '--force', $wt) | Out-Null
            Invoke-Git $Root @('branch', '-D', $tb) | Out-Null
            Stop-Orq 5 'Failed to start conflict-resolution merge.' @{ git = $m.Msg }
        }
        $extras = Add-Extras $wt $rec
        $conf = @(Get-Lines (Invoke-Git $wt @('diff', '--name-only', '--diff-filter=U')).Out)
        $autoMerged = @(Get-Lines (Invoke-Git $wt @('diff', '--name-only', '--cached')).Out)
        Write-Result @{
            task = $Task; branch = $tb; worktree = $wt; fromTask = $FromTask; fromBranch = $fb
            conflicts = $conf; autoMerged = $autoMerged; extras = $extras
        }
    }

    'commit' {
        Assert-Name $Slug 'Slug'; Assert-Name $Task 'Task'
        if (-not $Message) { Stop-Orq 2 'Missing -Message.' }
        $rec = Read-Record
        $wt = Get-WtPath $rec $Task
        if (-not (Test-Path -LiteralPath $wt)) { Stop-Orq 2 "Worktree not found: $wt" }
        $allowed = @(Split-List $Files | ForEach-Object { ConvertTo-RelPath $_ })
        if ($allowed.Count -eq 0) { Stop-Orq 2 'Missing -Files (comma-separated WRITABLE FILES; folders end with /).' }

        $copyPaths = @(); $linkDirs = @()
        foreach ($e in (Get-ExtraEntries $wt)) {
            $kind, $rel = $e -split '\|', 2
            $norm = ConvertTo-RelPath $rel
            if ($kind -eq 'link') { $linkDirs += $norm } else { $copyPaths += $norm }
        }
        $entries = @(Get-StatusEntries $wt $copyPaths $linkDirs)
        $inMerge = (Invoke-Git $wt @('rev-parse', '-q', '--verify', 'MERGE_HEAD')).Code -eq 0

        if ($entries.Count -eq 0 -and -not $inMerge) {
            Write-Result @{ status = 'EMPTY'; task = $Task; branch = (Get-Branch $Task); message = 'No changes to commit.' }
        }

        $allPaths = New-Object System.Collections.Generic.List[string]
        $toStage = New-Object System.Collections.Generic.List[string]
        $outside = @()

        foreach ($ent in $entries) {
            if (-not $allPaths.Contains($ent.Path)) { $allPaths.Add($ent.Path) }
            if ($ent.Orig -and -not $allPaths.Contains($ent.Orig)) { $allPaths.Add($ent.Orig) }

            if (-not $inMerge) {
                if (-not (Test-Allowed $ent.Path $allowed)) { $outside += $ent.Path }
                if ($ent.Orig -and -not (Test-Allowed $ent.Orig $allowed)) { $outside += $ent.Orig }
                if (-not $toStage.Contains($ent.Path)) { $toStage.Add($ent.Path) }
                if ($ent.Orig -and -not $toStage.Contains($ent.Orig)) { $toStage.Add($ent.Orig) }
            }
            else {
                $isUnmerged = ($ent.XY -match 'U|DD|AA')
                $isDirtyWt = ($ent.XY[1] -ne ' ')
                if ($isUnmerged -or $isDirtyWt) {
                    if (-not (Test-Allowed $ent.Path $allowed)) { $outside += $ent.Path }
                    if ($ent.Orig -and -not (Test-Allowed $ent.Orig $allowed)) { $outside += $ent.Orig }
                    if (-not $toStage.Contains($ent.Path)) { $toStage.Add($ent.Path) }
                    if ($ent.Orig -and -not $toStage.Contains($ent.Orig)) { $toStage.Add($ent.Orig) }
                }
            }
        }

        $outside = @($outside | Select-Object -Unique)
        if ($outside.Count -gt 0) {
            Stop-Orq 3 'Changes outside WRITABLE FILES; nothing committed.' @{ task = $Task; outOfScope = $outside; changed = $allPaths.ToArray() }
        }
        $sensitive = @($allPaths | Where-Object { $_ -match $SensitiveRegex })
        if ($sensitive.Count -gt 0) {
            Stop-Orq 3 'Sensitive-looking files changed; nothing committed.' @{ task = $Task; sensitive = $sensitive }
        }

        if ($inMerge) {
            $unresolvedMarkers = @()
            foreach ($ent in $entries) {
                if ($ent.XY -match 'U|DD|AA') {
                    $disk = Join-Path $wt ($ent.Path -replace '/', '\')
                    if (Test-Path -LiteralPath $disk -PathType Leaf) {
                        if (Select-String -LiteralPath $disk -Pattern '^(<<<<<<< |=======\r?$|>>>>>>> )' -Quiet) {
                            $unresolvedMarkers += $ent.Path
                        }
                    }
                }
            }
            if ($unresolvedMarkers.Count -gt 0) {
                Stop-Orq 4 'Conflict markers still present in files; nothing committed.' @{ task = $Task; files = $unresolvedMarkers }
            }
        }

        foreach ($p in $toStage) {
            $disk = Join-Path $wt ($p -replace '/', '\')
            if (Test-Path -LiteralPath $disk) {
                $r = Invoke-Git $wt @('add', '--', $p)
            }
            else {
                $r = Invoke-Git $wt @('rm', '-f', '--quiet', '--ignore-unmatch', '--', $p)
            }
            if ($r.Code -ne 0) { Stop-Orq 5 "git add/rm failed for '$p'." @{ git = $r.Msg } }
        }

        if ($inMerge) {
            $stillUnmerged = @(Get-Lines (Invoke-Git $wt @('diff', '--name-only', '--diff-filter=U')).Out)
            if ($stillUnmerged.Count -gt 0) {
                Stop-Orq 4 'Unresolved index entries remain; nothing committed.' @{ task = $Task; unresolved = $stillUnmerged }
            }
        }

        $tmp = [System.IO.Path]::GetTempFileName()
        try {
            [System.IO.File]::WriteAllText($tmp, $Message, (New-Object System.Text.UTF8Encoding $false))
            $r = Invoke-Git $wt @('commit', '-F', $tmp)
        }
        finally { try { if (Test-Path -LiteralPath $tmp) { [System.IO.File]::Delete($tmp) } } catch { } }
        if ($r.Code -ne 0) { Stop-Orq 5 'git commit failed (files remain staged in the worktree).' @{ git = $r.Msg } }
        Write-Result @{ task = $Task; branch = (Get-Branch $Task); commit = (Get-GitValue $wt @('rev-parse', 'HEAD')); files = $allPaths.ToArray(); mergeCommit = $inMerge }
    }

    'integrate' {
        Assert-Name $Slug 'Slug'; Assert-Name $Task 'Task'
        if ($Task -eq $IntName) { Stop-Orq 2 "Cannot integrate '$IntName' into itself." }
        $rec = Read-Record
        $ib = Get-Branch $IntName; $tb = Get-Branch $Task; $intWt = Get-WtPath $rec $IntName
        if (-not (Test-Branch $tb)) { Stop-Orq 2 "Branch not found: $tb" }
        $dirty = Get-GitValue $intWt @('status', '--porcelain', '--untracked-files=no')
        if ($dirty) { Stop-Orq 2 'Integration worktree has uncommitted tracked changes.' @{ dirty = @(Get-Lines $dirty) } }
        $ahead = [int](Get-GitValue $Root @('rev-list', '--count', "$ib..$tb"))
        if ($ahead -eq 0) { Write-Result @{ status = 'NOOP'; task = $Task; message = 'Nothing to merge.' } }
        $stat = (Invoke-Git $Root @('diff', '--stat', "$ib...$tb")).Out.Trim()
        $sha = Invoke-SafeMerge $intWt $tb "merge($Task): $Slug" @{ task = $Task; diffStat = $stat }
        Write-Result @{ task = $Task; integrationBranch = $ib; mergeCommit = $sha; commitsMerged = $ahead }
    }

    'status' {
        Assert-Name $Slug 'Slug'
        $rec = Read-Record
        $ib = Get-Branch $IntName
        $wtMap = Get-WorktreeMap
        $tasks = @()
        foreach ($b in (Get-Lines (Get-GitValue $Root @('for-each-ref', '--format=%(refname:short)', "refs/heads/orq/$Slug/")))) {
            if ($b -eq $ib) { continue }
            $tasks += [ordered]@{
                task = $b.Substring("orq/$Slug/".Length); branch = $b
                sha = (Get-GitValue $Root @('rev-parse', '--short', $b))
                merged = (Test-Ancestor $b $ib)
                aheadOfIntegration = [int](Get-GitValue $Root @('rev-list', '--count', "$ib..$b"))
                worktree = $wtMap[$b]
            }
        }
        $integration = $null
        if (Test-Branch $ib) {
            $integration = [ordered]@{
                branch = $ib; sha = (Get-GitValue $Root @('rev-parse', '--short', $ib)); worktree = $wtMap[$ib]
                commitsSinceBase = [int](Get-GitValue $Root @('rev-list', '--count', "$($rec.baseSha)..$ib"))
                mergedIntoBase = (Test-Ancestor $ib $rec.base)
            }
        }
        Write-Result @{ slug = $Slug; base = $rec.base; baseSha = $rec.baseSha; integration = $integration; tasks = $tasks }
    }

    'list' {
        $refs = Get-Lines (Get-GitValue $Root @('for-each-ref', '--format=%(refname:short)|%(committerdate:iso8601)', 'refs/heads/orq/'))
        $names = @($refs | ForEach-Object { ($_ -split '\|', 2)[0] })
        $items = @()
        foreach ($line in $refs) {
            $name, $date = $line -split '\|', 2
            if ($name -match '^orq/([^/]+)/integration$') {
                $s = $Matches[1]
                $items += [ordered]@{
                    slug = $s; lastCommit = $date
                    taskBranches = @($names | Where-Object { $_ -like "orq/$s/*" -and $_ -ne $name }).Count
                    hasRecord = (Test-Path -LiteralPath (Join-Path (Join-Path $CommonDir 'orq') "$s.json"))
                }
            }
        }
        Write-Result @{ repo = $Root; requests = $items }
    }

    'finalize' {
        Assert-Name $Slug 'Slug'
        $rec = Read-Record
        $ib = Get-Branch $IntName
        if (-not (Test-Branch $ib)) { Stop-Orq 2 "Branch not found: $ib" }
        $summary = @{
            slug = $Slug; integrationBranch = $ib; base = $rec.base; mode = $Mode
            commitsSinceBase = [int](Get-GitValue $Root @('rev-list', '--count', "$($rec.baseSha)..$ib"))
            log = @(Get-Lines (Get-GitValue $Root @('log', '--oneline', '--first-parent', "$($rec.baseSha)..$ib")))
        }
        if ($Mode -eq 'push') {
            $remote = Invoke-Git $Root @('remote', 'get-url', 'origin')
            if ($remote.Code -ne 0) { Stop-Orq 2 'No origin remote configured.' }
            $p = Invoke-Git $Root @('push', '-u', 'origin', $ib)
            if ($p.Code -ne 0) { Stop-Orq 5 'Push failed (no force-push attempted).' @{ git = $p.Msg } }
            $summary['pushed'] = $true
            $summary['remoteUrl'] = $remote.Out.Trim()
        }
        elseif ($Mode -eq 'merge') {
            $cur = Get-GitValue $Root @('branch', '--show-current')
            if ($cur -ne $rec.base) { Stop-Orq 2 "Main working copy must be on '$($rec.base)' (currently '$cur')." }
            $dirty = Get-GitValue $Root @('status', '--porcelain', '--untracked-files=no')
            if ($dirty) { Stop-Orq 2 'Main working copy has uncommitted tracked changes.' @{ dirty = @(Get-Lines $dirty) } }
            $summary['mergeCommit'] = Invoke-SafeMerge $Root $ib "merge(orq): $Slug" @{ integrationBranch = $ib }
            $summary['merged'] = $true
        }
        Write-Result $summary
    }

    'cleanup' {
        Assert-Name $Slug 'Slug'
        if (-not $All -and -not $Task) { Stop-Orq 2 'Use -Task <id> or -All.' }
        $rec = Read-Record
        $ib = Get-Branch $IntName
        $wtMap = Get-WorktreeMap
        if ($All) {
            $targets = @(Get-Lines (Get-GitValue $Root @('for-each-ref', '--format=%(refname:short)', "refs/heads/orq/$Slug/")) | Where-Object { $_ -ne $ib })
            if (Test-Branch $ib) { $targets += $ib }
        }
        else { Assert-Name $Task 'Task'; $targets = @(Get-Branch $Task) }

        $removed = @(); $kept = @()
        foreach ($b in $targets) {
            if (-not (Test-Branch $b)) { $kept += [ordered]@{ branch = $b; reason = 'branch not found' }; continue }
            if ($b -eq $ib) { $isMerged = Test-Ancestor $b $rec.base; $mergedInto = $rec.base; $allowForce = [bool]$Discard }
            else { $isMerged = Test-Ancestor $b $ib; $mergedInto = $ib; $allowForce = [bool]($Force -or $Discard) }
            if (-not $isMerged -and -not $allowForce) {
                $kept += [ordered]@{ branch = $b; reason = "not merged into $mergedInto" }; continue
            }
            $wt = $wtMap[$b]
            if ($wt) {
                Remove-Extras $wt
                $wtArgs = @('worktree', 'remove'); if ($Force -or $Discard) { $wtArgs += '--force' }
                $r = Invoke-Git $Root ($wtArgs + @($wt))
                if ($r.Code -ne 0) { $kept += [ordered]@{ branch = $b; reason = "worktree not removed: $($r.Msg)" }; continue }
            }
            # Safe: merge status was verified above (or -Force/-Discard was explicitly passed).
            $r = Invoke-Git $Root @('branch', '-D', $b)
            if ($r.Code -ne 0) { $kept += [ordered]@{ branch = $b; reason = $r.Msg }; continue }
            $removed += $b
        }
        Invoke-Git $Root @('worktree', 'prune') | Out-Null
        $closed = $false
        if ($All -and -not (Test-Branch $ib)) {
            Invoke-Git $Root @('tag', '-d', "orq/$Slug/base") | Out-Null
            $rp = Get-RecordPath
            try { if (Test-Path -LiteralPath $rp) { [System.IO.File]::Delete($rp) } } catch { }
            if ((Test-Path -LiteralPath $rec.wtBase) -and -not (Get-ChildItem -LiteralPath $rec.wtBase -Force)) { [System.IO.Directory]::Delete($rec.wtBase, $false) }
            $closed = $true
        }
        Write-Result @{ slug = $Slug; removed = $removed; kept = $kept; requestClosed = $closed }
    }
}
