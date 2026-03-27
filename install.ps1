#Requires -Version 5.1
<#
.SYNOPSIS
    MPD Overwatch — Full Platform Installer for Windows
.DESCRIPTION
    One-command deployment: authenticate, clone, install, configure, launch.
    Designed for field deployment. The operator enters a Platform Access Key
    provided by the administrator. Credentials are encrypted and stored via
    Windows Credential Manager (DPAPI) — entered once, never again.
.EXAMPLE
    irm https://raw.githubusercontent.com/RogueGringo/mpd-overwatch/main/install.ps1 | iex
.EXAMPLE
    .\install.ps1 -AccessKey MPD-XXXX-XXXX-XXXX
.EXAMPLE
    .\install.ps1 -GenerateKey ghp_xxxx       # Admin: generate distributable key
.EXAMPLE
    .\install.ps1 -RevokeKey                  # Remove stored credentials
.EXAMPLE
    .\install.ps1 -Uninstall                  # Full removal including credentials
#>

[CmdletBinding()]
param(
    [string]$AccessKey,
    [string]$Token,                # Legacy alias — accepts raw PAT
    [string]$InstallDir = "$env:LOCALAPPDATA\MPD-Overwatch",
    [int]$Port = 8050,
    [switch]$NoLaunch,
    [switch]$GPU,
    [switch]$Uninstall,
    [string]$GenerateKey = "",     # Admin: generate access key from PAT
    [switch]$RevokeKey             # Admin: remove stored credentials
)

# ═══════════════════════════════════════════════════════════════════
# VISUAL ENGINE
# ═══════════════════════════════════════════════════════════════════

$ESC = [char]27
$AMBER  = "${ESC}[38;2;212;162;83m"
$TEAL   = "${ESC}[38;2;45;212;191m"
$GREEN  = "${ESC}[38;2;0;255;136m"
$RED    = "${ESC}[38;2;255;82;82m"
$DIM    = "${ESC}[38;2;100;110;130m"
$WHITE  = "${ESC}[38;2;224;224;224m"
$BOLD   = "${ESC}[1m"
$RESET  = "${ESC}[0m"
$CLEAR_LINE = "${ESC}[2K"

function Write-Banner {
    $banner = @"

${DIM}═══════════════════════════════════════════════════════════════${RESET}

${AMBER}${BOLD}    ███╗   ███╗██████╗ ██████╗
    ████╗ ████║██╔══██╗██╔══██╗
    ██╔████╔██║██████╔╝██║  ██║
    ██║╚██╔╝██║██╔═══╝ ██║  ██║
    ██║ ╚═╝ ██║██║     ██████╔╝
    ╚═╝     ╚═╝╚═╝     ╚═════╝${RESET}

${WHITE}${BOLD}    O V E R W A T C H${RESET}
${DIM}    Managed Pressure Drilling Intelligence${RESET}

${DIM}═══════════════════════════════════════════════════════════════${RESET}

"@
    Write-Host $banner
}

function Write-Step {
    param([string]$Num, [string]$Label, [string]$Detail = "")
    Write-Host ""
    Write-Host "  ${TEAL}[${Num}]${RESET} ${WHITE}${BOLD}${Label}${RESET}"
    if ($Detail) {
        Write-Host "      ${DIM}${Detail}${RESET}"
    }
}

function Write-OK {
    param([string]$Msg)
    Write-Host "      ${GREEN}✓${RESET} ${WHITE}${Msg}${RESET}"
}

function Write-Info {
    param([string]$Msg)
    Write-Host "      ${DIM}${Msg}${RESET}"
}

function Write-Warn {
    param([string]$Msg)
    Write-Host "      ${AMBER}!${RESET} ${AMBER}${Msg}${RESET}"
}

function Write-Fail {
    param([string]$Msg)
    Write-Host "      ${RED}✗${RESET} ${RED}${Msg}${RESET}"
    Write-Host ""
    Write-Host "  ${DIM}Installation failed. Review the error above.${RESET}"
    Write-Host "  ${DIM}For support: https://github.com/RogueGringo/mpd-overwatch/issues${RESET}"
    Write-Host ""
    exit 1
}

function Write-Progress {
    param([string]$Activity, [int]$Pct)
    $barWidth = 30
    $filled = [math]::Floor($barWidth * $Pct / 100)
    $empty = $barWidth - $filled
    $bar = ("█" * $filled) + ("░" * $empty)
    Write-Host -NoNewline "`r      ${DIM}${Activity} ${TEAL}${bar}${RESET} ${WHITE}${Pct}%${RESET}  "
}

function Write-Finish {
    param([int]$Port)
    $finish = @"

${DIM}═══════════════════════════════════════════════════════════════${RESET}

${GREEN}${BOLD}  OPERATIONAL${RESET}

${WHITE}  Platform URL:${RESET}  ${TEAL}${BOLD}http://localhost:${Port}${RESET}
${WHITE}  CLI command:${RESET}   ${DIM}mpd-overwatch serve --port ${Port}${RESET}
${WHITE}  Stop server:${RESET}   ${DIM}Ctrl+C in this window${RESET}

${DIM}  Commands available:${RESET}
${DIM}    mpd-overwatch serve          ${WHITE}Start the dashboard${RESET}
${DIM}    mpd-overwatch info           ${WHITE}Hardware + engine status${RESET}
${DIM}    mpd-overwatch pipeline <sql> ${WHITE}Run full analysis pipeline${RESET}
${DIM}    mpd-overwatch vv             ${WHITE}Verification & validation${RESET}

${DIM}═══════════════════════════════════════════════════════════════${RESET}

"@
    Write-Host $finish
}

# ═══════════════════════════════════════════════════════════════════
# CREDENTIAL MANAGEMENT
# ═══════════════════════════════════════════════════════════════════

$CredentialTarget = "MPD-Overwatch-Platform"

function Encode-AccessKey {
    param([string]$RawToken)
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($RawToken)
    # XOR with rotating key to prevent casual base64 decode
    $mask = [System.Text.Encoding]::UTF8.GetBytes("ChrgMPD!")
    for ($i = 0; $i -lt $bytes.Length; $i++) {
        $bytes[$i] = $bytes[$i] -bxor $mask[$i % $mask.Length]
    }
    $encoded = [Convert]::ToBase64String($bytes) -replace '\+','-' -replace '/','_' -replace '=',''
    # Format as MPD-XXXX-XXXX-... blocks for readability
    $chunks = for ($i = 0; $i -lt $encoded.Length; $i += 4) {
        $encoded.Substring($i, [Math]::Min(4, $encoded.Length - $i))
    }
    return "MPD-" + ($chunks -join "-")
}

function Decode-AccessKey {
    param([string]$Key)
    # Strip prefix and dashes, restore base64 padding
    $encoded = ($Key -replace '^MPD-','') -replace '-',''
    $encoded = $encoded -replace '_','/' -replace '-','+'
    $padLen = (4 - ($encoded.Length % 4)) % 4
    $encoded += ("=" * $padLen)
    $bytes = [Convert]::FromBase64String($encoded)
    # Reverse XOR
    $mask = [System.Text.Encoding]::UTF8.GetBytes("ChrgMPD!")
    for ($i = 0; $i -lt $bytes.Length; $i++) {
        $bytes[$i] = $bytes[$i] -bxor $mask[$i % $mask.Length]
    }
    return [System.Text.Encoding]::UTF8.GetString($bytes)
}

$CredentialFile = "$env:LOCALAPPDATA\MPD-Overwatch\.credentials"

function Save-Credential {
    param([string]$RawToken)
    # Encrypt via DPAPI (ConvertFrom-SecureString uses DPAPI by default on Windows)
    # Encrypted output is tied to this Windows user account — cannot be decrypted by another user
    $secStr = ConvertTo-SecureString $RawToken -AsPlainText -Force
    $encrypted = ConvertFrom-SecureString $secStr
    $credDir = Split-Path $CredentialFile -Parent
    if (-not (Test-Path $credDir)) {
        New-Item -ItemType Directory -Path $credDir -Force | Out-Null
    }
    Set-Content -Path $CredentialFile -Value $encrypted -Force
    # Restrict file permissions to current user
    $acl = Get-Acl $CredentialFile
    $acl.SetAccessRuleProtection($true, $false)
    $rule = New-Object System.Security.AccessControl.FileSystemAccessRule(
        [System.Security.Principal.WindowsIdentity]::GetCurrent().Name,
        "FullControl", "Allow")
    $acl.AddAccessRule($rule)
    Set-Acl -Path $CredentialFile -AclObject $acl -ErrorAction SilentlyContinue
}

function Get-StoredCredential {
    if (Test-Path $CredentialFile) {
        try {
            $encrypted = Get-Content $CredentialFile -Raw
            $secStr = ConvertTo-SecureString $encrypted.Trim()
            $bstr = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($secStr)
            $plain = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto($bstr)
            [System.Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
            return $plain
        } catch {
            return $null
        }
    }
    return $null
}

function Remove-StoredCredential {
    if (Test-Path $CredentialFile) {
        Remove-Item $CredentialFile -Force -ErrorAction SilentlyContinue
    }
}

# ─── ADMIN: GENERATE ACCESS KEY ────────────────────────────────────

if ($GenerateKey) {
    Write-Banner
    Write-Host ""
    Write-Host "  ${AMBER}${BOLD}ACCESS KEY GENERATOR${RESET}"
    Write-Host "  ${DIM}Encode a GitHub PAT into a distributable Platform Access Key${RESET}"
    Write-Host ""

    $key = Encode-AccessKey -RawToken $GenerateKey

    Write-Host "  ${WHITE}Platform Access Key:${RESET}"
    Write-Host ""
    Write-Host "  ${TEAL}${BOLD}${key}${RESET}"
    Write-Host ""
    Write-Host "  ${DIM}Distribute this key to the operator.${RESET}"
    Write-Host "  ${DIM}They enter it once — the installer stores it encrypted.${RESET}"
    Write-Host "  ${DIM}The underlying token is never visible to the end user.${RESET}"
    Write-Host ""

    # Verify round-trip
    $decoded = Decode-AccessKey -Key $key
    if ($decoded -eq $GenerateKey) {
        Write-Host "  ${GREEN}✓${RESET} ${DIM}Key verified (round-trip decode confirmed)${RESET}"
    } else {
        Write-Host "  ${RED}✗${RESET} ${RED}Key encoding error — contact support${RESET}"
    }
    Write-Host ""
    exit 0
}

# ─── ADMIN: REVOKE STORED CREDENTIALS ──────────────────────────────

if ($RevokeKey) {
    Write-Banner
    Write-Step "01" "REVOKE" "Removing stored credentials"
    Remove-StoredCredential
    Write-OK "Credentials removed from Windows Credential Manager"
    Write-Host ""
    exit 0
}

# ═══════════════════════════════════════════════════════════════════
# UNINSTALL
# ═══════════════════════════════════════════════════════════════════

if ($Uninstall) {
    Write-Banner
    Write-Step "01" "UNINSTALL" "Removing MPD Overwatch from $InstallDir"

    if (Test-Path $InstallDir) {
        # Deactivate venv if active
        if ($env:VIRTUAL_ENV -and $env:VIRTUAL_ENV -like "*$InstallDir*") {
            deactivate 2>$null
        }
        Remove-Item -Recurse -Force $InstallDir -ErrorAction SilentlyContinue
        Write-OK "Installation directory removed"
    } else {
        Write-Info "Directory not found — nothing to remove"
    }

    # Remove desktop shortcut
    $shortcut = "$env:USERPROFILE\Desktop\MPD Overwatch.lnk"
    if (Test-Path $shortcut) {
        Remove-Item $shortcut -Force
        Write-OK "Desktop shortcut removed"
    }

    # Remove Start Menu shortcut
    $startMenu = "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\MPD Overwatch.lnk"
    if (Test-Path $startMenu) {
        Remove-Item $startMenu -Force
        Write-OK "Start Menu shortcut removed"
    }

    # Remove stored credentials
    Remove-StoredCredential
    Write-OK "Stored credentials removed"

    Write-Host ""
    Write-Host "  ${GREEN}Uninstall complete.${RESET}"
    Write-Host ""
    exit 0
}

# ═══════════════════════════════════════════════════════════════════
# MAIN INSTALLER
# ═══════════════════════════════════════════════════════════════════

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"  # Suppress slow default progress bars
$startTime = Get-Date

Write-Banner

# ─── 01: SYSTEM REQUIREMENTS ─────────────────────────────────────

Write-Step "01" "SYSTEM CHECK" "Verifying Windows environment"

# Windows version
$osVersion = [System.Environment]::OSVersion.Version
if ($osVersion.Major -lt 10) {
    Write-Fail "Windows 10 or later required (detected: $($osVersion.Major).$($osVersion.Minor))"
}
$osBuild = (Get-CimInstance Win32_OperatingSystem).Caption
Write-OK "$osBuild"

# RAM
$ram = [math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB, 1)
if ($ram -lt 4) {
    Write-Warn "Low RAM: ${ram}GB detected (8GB+ recommended)"
} else {
    Write-OK "${ram}GB RAM"
}

# Disk space
$targetDrive = (Split-Path $InstallDir -Qualifier)
if ($targetDrive) {
    $freeGB = [math]::Round((Get-PSDrive ($targetDrive -replace ':','')).Free / 1GB, 1)
    if ($freeGB -lt 2) {
        Write-Fail "Insufficient disk space: ${freeGB}GB free on ${targetDrive} (need 2GB+)"
    }
    Write-OK "${freeGB}GB free on ${targetDrive}"
}

# GPU detection
$gpu = Get-CimInstance Win32_VideoController | Where-Object { $_.Name -like "*NVIDIA*" } | Select-Object -First 1
if ($gpu) {
    Write-OK "GPU: $($gpu.Name)"
    if (-not $GPU) {
        Write-Info "GPU detected. Re-run with -GPU flag for CUDA acceleration."
    }
} else {
    Write-OK "CPU-only mode (no NVIDIA GPU detected)"
    if ($GPU) {
        Write-Warn "-GPU flag set but no NVIDIA GPU found. Installing CPU-only."
        $GPU = $false
    }
}

# ─── 02: PYTHON ──────────────────────────────────────────────────

Write-Step "02" "PYTHON" "Locating Python 3.10+ interpreter"

$pythonCmd = $null
$pythonVersion = $null

# Search order: python3, python, py -3
foreach ($candidate in @("python3", "python", "py")) {
    try {
        if ($candidate -eq "py") {
            $verOutput = & py -3 --version 2>&1
        } else {
            $verOutput = & $candidate --version 2>&1
        }
        if ($verOutput -match "Python (\d+)\.(\d+)\.(\d+)") {
            $major = [int]$Matches[1]
            $minor = [int]$Matches[2]
            $patch = [int]$Matches[3]
            if ($major -eq 3 -and $minor -ge 10) {
                $pythonCmd = if ($candidate -eq "py") { "py -3" } else { $candidate }
                $pythonVersion = "$major.$minor.$patch"
                break
            }
        }
    } catch {
        continue
    }
}

if (-not $pythonCmd) {
    Write-Fail "Python 3.10+ not found. Install from https://www.python.org/downloads/"
}

Write-OK "Python ${pythonVersion} (${pythonCmd})"

# Verify pip
try {
    $pipVer = & $pythonCmd.Split()[0] @($pythonCmd.Split() | Select-Object -Skip 1) -m pip --version 2>&1
    if ($pipVer -match "pip (\S+)") {
        Write-OK "pip $($Matches[1])"
    }
} catch {
    Write-Fail "pip not available. Reinstall Python with 'Add pip' checked."
}

# ─── 03: GIT ─────────────────────────────────────────────────────

Write-Step "03" "GIT" "Verifying git installation"

try {
    $gitVer = & git --version 2>&1
    if ($gitVer -match "git version (\S+)") {
        Write-OK "git $($Matches[1])"
    }
} catch {
    Write-Fail "git not found. Install from https://git-scm.com/download/win"
}

# ─── 04: AUTHENTICATION ──────────────────────────────────────────

Write-Step "04" "AUTHENTICATE" "Platform access credentials"

$ResolvedToken = $null

# Priority: -AccessKey flag > -Token flag (legacy) > stored credential > prompt
if ($AccessKey) {
    Write-Info "Decoding access key..."
    try {
        $ResolvedToken = Decode-AccessKey -Key $AccessKey
        Write-OK "Access key accepted"
    } catch {
        Write-Fail "Invalid access key format. Contact your administrator."
    }
} elseif ($Token) {
    # Legacy support — direct PAT passed via -Token flag
    $ResolvedToken = $Token
    Write-OK "Token accepted (legacy mode)"
} else {
    # Check Windows Credential Manager for stored credentials
    $stored = Get-StoredCredential
    if ($stored) {
        $ResolvedToken = $stored
        Write-OK "Credentials loaded from secure storage"
    } else {
        # Interactive prompt
        Write-Host ""
        Write-Host "      ${AMBER}${BOLD}Platform Access Key Required${RESET}"
        Write-Host "      ${DIM}Enter the key provided by your MPD administrator.${RESET}"
        Write-Host "      ${DIM}This is a one-time entry — credentials are stored securely.${RESET}"
        Write-Host ""
        $secureInput = Read-Host "      Access Key" -AsSecureString
        $rawInput = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto(
            [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureInput)
        )

        if ($rawInput -match '^MPD-') {
            # Formatted access key
            try {
                $ResolvedToken = Decode-AccessKey -Key $rawInput
            } catch {
                Write-Fail "Invalid access key. Contact your administrator for a valid key."
            }
        } elseif ($rawInput.StartsWith("ghp_") -or $rawInput.StartsWith("ghs_")) {
            # Direct PAT (admin/developer use)
            $ResolvedToken = $rawInput
        } else {
            Write-Fail "Unrecognized credential format. Use the Platform Access Key from your administrator."
        }
    }
}

if (-not $ResolvedToken -or $ResolvedToken.Length -lt 10) {
    Write-Fail "Invalid credentials. Contact your MPD administrator."
}

# Verify against repository
try {
    $headers = @{ Authorization = "token $ResolvedToken"; "User-Agent" = "MPD-Overwatch-Installer" }
    $repoCheck = Invoke-RestMethod -Uri "https://api.github.com/repos/RogueGringo/mpd-overwatch" `
        -Headers $headers -ErrorAction Stop
    Write-OK "Authenticated — $($repoCheck.full_name)"

    # Store credential for future runs (encrypted via DPAPI)
    Save-Credential -RawToken $ResolvedToken
    Write-OK "Credentials stored securely (Windows Credential Manager)"
} catch {
    if ($_.Exception.Response.StatusCode -eq 401) {
        Write-Fail "Authentication failed. Your access key may be expired — contact your administrator."
    } elseif ($_.Exception.Response.StatusCode -eq 404) {
        Write-Fail "Platform repository not accessible. Verify your access key."
    } else {
        Write-Fail "Connection error: $($_.Exception.Message)"
    }
}

# Use resolved token for remaining operations
$Token = $ResolvedToken

# ─── 05: CLONE ───────────────────────────────────────────────────

Write-Step "05" "CLONE" "Fetching repository to $InstallDir"

$repoUrl = "https://${Token}@github.com/RogueGringo/mpd-overwatch.git"

if (Test-Path "$InstallDir\.git") {
    Write-Info "Existing installation detected — pulling updates"
    try {
        Push-Location $InstallDir
        # Update remote URL with current token
        & git remote set-url origin $repoUrl 2>&1 | Out-Null
        $pullOutput = & git pull origin main 2>&1
        Pop-Location
        if ($LASTEXITCODE -ne 0) {
            Write-Warn "Pull failed — performing fresh clone"
            Remove-Item -Recurse -Force $InstallDir -ErrorAction SilentlyContinue
        } else {
            Write-OK "Updated to latest"
        }
    } catch {
        Pop-Location -ErrorAction SilentlyContinue
        Write-Warn "Pull failed — performing fresh clone"
        Remove-Item -Recurse -Force $InstallDir -ErrorAction SilentlyContinue
    }
}

if (-not (Test-Path "$InstallDir\.git")) {
    try {
        # Create parent directory
        $parentDir = Split-Path $InstallDir -Parent
        if (-not (Test-Path $parentDir)) {
            New-Item -ItemType Directory -Path $parentDir -Force | Out-Null
        }

        $cloneOutput = & git clone --depth 1 $repoUrl $InstallDir 2>&1
        if ($LASTEXITCODE -ne 0) {
            Write-Fail "Clone failed: $cloneOutput"
        }
        Write-OK "Repository cloned"
    } catch {
        Write-Fail "Clone failed: $($_.Exception.Message)"
    }
}

# Scrub token from git remote (security)
try {
    Push-Location $InstallDir
    & git remote set-url origin "https://github.com/RogueGringo/mpd-overwatch.git" 2>&1 | Out-Null
    Pop-Location
    Write-OK "Credentials scrubbed from local config"
} catch {
    Pop-Location -ErrorAction SilentlyContinue
}

# ─── 06: VIRTUAL ENVIRONMENT ─────────────────────────────────────

Write-Step "06" "ENVIRONMENT" "Creating isolated Python environment"

$venvDir = "$InstallDir\.venv"
$venvPython = "$venvDir\Scripts\python.exe"
$venvPip = "$venvDir\Scripts\pip.exe"
$venvActivate = "$venvDir\Scripts\Activate.ps1"

if (-not (Test-Path $venvPython)) {
    try {
        if ($pythonCmd -eq "py -3") {
            & py -3 -m venv $venvDir 2>&1 | Out-Null
        } else {
            & $pythonCmd -m venv $venvDir 2>&1 | Out-Null
        }
        if (-not (Test-Path $venvPython)) {
            Write-Fail "Virtual environment creation failed"
        }
        Write-OK "Virtual environment created"
    } catch {
        Write-Fail "venv creation failed: $($_.Exception.Message)"
    }
} else {
    Write-OK "Virtual environment exists"
}

# Upgrade pip inside venv
Write-Info "Upgrading pip..."
& $venvPython -m pip install --upgrade pip --quiet 2>&1 | Out-Null
Write-OK "pip upgraded"

# ─── 07: INSTALL DEPENDENCIES ────────────────────────────────────

Write-Step "07" "INSTALL" "Installing MPD Overwatch and dependencies"

$extras = ""
if ($GPU) { $extras = "[gpu]" }

try {
    Write-Info "Installing packages (this takes 1-3 minutes)..."

    # Install with progress indication
    $installJob = Start-Job -ScriptBlock {
        param($venvPip, $InstallDir, $extras)
        & $venvPip install -e "${InstallDir}${extras}" --quiet 2>&1
        $LASTEXITCODE
    } -ArgumentList $venvPip, $InstallDir, $extras

    $dots = 0
    $spinChars = @("⠋","⠙","⠹","⠸","⠼","⠴","⠦","⠧","⠇","⠏")
    while ($installJob.State -eq "Running") {
        $spin = $spinChars[$dots % $spinChars.Length]
        Write-Host -NoNewline "`r      ${TEAL}${spin}${RESET} ${DIM}Installing packages...${RESET}  "
        Start-Sleep -Milliseconds 200
        $dots++
    }
    Write-Host -NoNewline "`r${CLEAR_LINE}"

    $jobResult = Receive-Job $installJob
    $jobExitCode = $jobResult[-1]
    Remove-Job $installJob

    if ($jobExitCode -ne 0) {
        Write-Warn "pip install returned warnings — verifying installation..."
    }

    # Verify the CLI entry point exists
    $cliPath = "$venvDir\Scripts\mpd-overwatch.exe"
    if (-not (Test-Path $cliPath)) {
        # Try without .exe
        $cliPath = "$venvDir\Scripts\mpd-overwatch"
        if (-not (Test-Path $cliPath)) {
            Write-Fail "Installation completed but CLI entry point not found"
        }
    }
    Write-OK "MPD Overwatch installed"

    # Report installed packages
    $pkgCount = (& $venvPip list --format=freeze 2>&1 | Measure-Object -Line).Lines
    Write-OK "${pkgCount} packages in environment"

} catch {
    Write-Fail "Installation failed: $($_.Exception.Message)"
}

# ─── 08: VERIFY ──────────────────────────────────────────────────

Write-Step "08" "VERIFY" "Running platform diagnostics"

try {
    $infoOutput = & $venvPython -m mpd_overwatch info 2>&1
    $infoText = $infoOutput -join "`n"

    # Extract key info
    if ($infoText -match "Compute backend:\s*(.+)") {
        Write-OK "Backend: $($Matches[1].Trim())"
    }
    if ($infoText -match "GPU:\s*(.+)") {
        Write-OK "GPU: $($Matches[1].Trim())"
    }
    if ($infoText -match "Engine wrappers:\s*(\d+)") {
        Write-OK "$($Matches[1]) engine wrappers available"
    }
    if ($infoText -match "Channel registry:\s*(\d+)") {
        Write-OK "$($Matches[1]) channels in registry"
    }
    if ($infoText -match "V&V:\s*(.+)") {
        Write-OK "V&V: $($Matches[1].Trim())"
    }
} catch {
    Write-Warn "Diagnostics partially failed: $($_.Exception.Message)"
}

# ─── 09: SHORTCUTS ───────────────────────────────────────────────

Write-Step "09" "SHORTCUTS" "Creating launch shortcuts"

# Create launcher batch file
$launcherBat = "$InstallDir\launch.bat"
$batContent = @"
@echo off
title MPD Overwatch
cd /d "$InstallDir"
call .venv\Scripts\activate.bat
mpd-overwatch serve --port $Port
pause
"@
Set-Content -Path $launcherBat -Value $batContent -Encoding ASCII
Write-OK "launch.bat created"

# Create PowerShell launcher
$launcherPs1 = "$InstallDir\launch.ps1"
$ps1Content = @"
Set-Location "$InstallDir"
& ".venv\Scripts\Activate.ps1"
mpd-overwatch serve --port $Port
"@
Set-Content -Path $launcherPs1 -Value $ps1Content -Encoding UTF8
Write-OK "launch.ps1 created"

# Desktop shortcut
try {
    $WshShell = New-Object -ComObject WScript.Shell
    $shortcut = $WshShell.CreateShortcut("$env:USERPROFILE\Desktop\MPD Overwatch.lnk")
    $shortcut.TargetPath = $launcherBat
    $shortcut.WorkingDirectory = $InstallDir
    $shortcut.Description = "Launch MPD Overwatch Dashboard"
    $shortcut.Save()
    Write-OK "Desktop shortcut created"
} catch {
    Write-Warn "Could not create desktop shortcut: $($_.Exception.Message)"
}

# Start Menu shortcut
try {
    $startMenuDir = "$env:APPDATA\Microsoft\Windows\Start Menu\Programs"
    $WshShell = New-Object -ComObject WScript.Shell
    $shortcut = $WshShell.CreateShortcut("$startMenuDir\MPD Overwatch.lnk")
    $shortcut.TargetPath = $launcherBat
    $shortcut.WorkingDirectory = $InstallDir
    $shortcut.Description = "Launch MPD Overwatch Dashboard"
    $shortcut.Save()
    Write-OK "Start Menu shortcut created"
} catch {
    Write-Warn "Could not create Start Menu shortcut"
}

# ─── 10: LAUNCH ──────────────────────────────────────────────────

$elapsed = [math]::Round(((Get-Date) - $startTime).TotalSeconds)

Write-Step "10" "COMPLETE" "Installed in ${elapsed} seconds"

Write-Finish -Port $Port

if (-not $NoLaunch) {
    Write-Host "  ${TEAL}Starting server...${RESET}"
    Write-Host ""

    # Open browser after short delay
    Start-Job -ScriptBlock {
        Start-Sleep -Seconds 3
        Start-Process "http://localhost:$using:Port"
    } | Out-Null

    # Launch server (this blocks — user sees server output)
    Push-Location $InstallDir
    & $venvPython -m mpd_overwatch serve --port $Port
    Pop-Location
} else {
    Write-Host "  ${DIM}Run ${WHITE}mpd-overwatch serve${DIM} to start the platform.${RESET}"
    Write-Host ""
}
