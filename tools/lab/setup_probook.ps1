<#
SatHunterSDR home lab PC (HackRF generator) setup, Windows 10/11.

Run in an ADMIN PowerShell:
    Set-ExecutionPolicy -Scope Process Bypass -Force
    .\setup_probook.ps1

What it does (each step is skipped when already done):
  1. ZeroTier One, joins the lab network (tolgyfa, 3efa5cb78a73a190)
  2. OpenSSH server, key login for the lab PC (G7), port 22 open from the ZeroTier network only,
     PowerShell as the SSH shell
  3. Git, and the SatHunter-SDR repo (branch feat/m10-9k6) in %USERPROFILE%\SatHunter-SDR
  4. radioconda (hackrf_transfer, Python, numpy, scipy, matplotlib) in %USERPROFILE%\radioconda
  5. No sleep on mains power (the weekend runs)
  6. Zadig for the HackRF's WinUSB driver (one manual click), then hackrf_info
At the end it prints what to send back: user name, ZeroTier node ID and address, hackrf_info.
#>

$ErrorActionPreference = "Stop"
$Network = "3efa5cb78a73a190"
$LabKey = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAINqrcCCyaR1rA60H22t6TLihpUOnW6zFtyBSlVSe8Wql G7-lab"
$Branch = "feat/m10-9k6"
$Repo = "https://github.com/z2labs/SatHunter-SDR.git"
$Home_ = $env:USERPROFILE
$Conda = Join-Path $Home_ "radioconda"

function Step($t) { Write-Host "`n== $t" -ForegroundColor Cyan }
function Ok($t) { Write-Host "   $t" -ForegroundColor Green }
function Warn($t) { Write-Host "   $t" -ForegroundColor Yellow }

$admin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $admin) { throw "Run this in an ADMIN PowerShell (right click > Run as administrator)." }
if (-not (Get-Command winget -ErrorAction SilentlyContinue)) { throw "winget is missing: install 'App Installer' from the Microsoft Store, then run again." }

# ---------------------------------------------------------------------------------------------
Step "1. ZeroTier"
$zt = "${env:ProgramFiles(x86)}\ZeroTier\One\zerotier-cli.bat"
if (-not (Test-Path $zt)) {
    winget install --id ZeroTier.ZeroTierOne -e --accept-source-agreements --accept-package-agreements --silent
    Start-Sleep 10
}
if (-not (Test-Path $zt)) { throw "ZeroTier did not install ($zt missing)" }
& $zt join $Network | Out-Null
$node = ((& $zt info) -split " ")[2]
Ok "joined $Network, node ID $node (authorise it on my.zerotier.com if it is new)"

# ---------------------------------------------------------------------------------------------
Step "2. OpenSSH server"
$cap = Get-WindowsCapability -Online -Name "OpenSSH.Server*" | Select-Object -First 1
if ($cap.State -ne "Installed") { Add-WindowsCapability -Online -Name $cap.Name | Out-Null }
Set-Service sshd -StartupType Automatic
Start-Service sshd
# key login: administrators use the shared file with strict permissions
$isAdminUser = (Get-LocalGroupMember -Group (Get-LocalGroup -SID "S-1-5-32-544").Name -ErrorAction SilentlyContinue | Where-Object { $_.Name -like "*\$env:USERNAME" }) -ne $null
if ($isAdminUser) {
    $ak = "C:\ProgramData\ssh\administrators_authorized_keys"
    if (-not (Test-Path $ak) -or -not (Select-String -Path $ak -SimpleMatch $LabKey.Split(" ")[1] -Quiet)) { Add-Content -Path $ak -Value $LabKey -Encoding ascii }
    icacls $ak /inheritance:r /grant "*S-1-5-32-544:F" /grant "SYSTEM:F" | Out-Null
} else {
    $d = Join-Path $Home_ ".ssh"; New-Item -ItemType Directory -Force $d | Out-Null
    $ak = Join-Path $d "authorized_keys"
    if (-not (Test-Path $ak) -or -not (Select-String -Path $ak -SimpleMatch $LabKey.Split(" ")[1] -Quiet)) { Add-Content -Path $ak -Value $LabKey -Encoding ascii }
}
Ok "lab key in $ak"
New-ItemProperty -Path "HKLM:\SOFTWARE\OpenSSH" -Name DefaultShell -Value "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" -PropertyType String -Force | Out-Null
if (-not (Get-NetFirewallRule -Name "SatHunter-SSH-ZeroTier" -ErrorAction SilentlyContinue)) {
    New-NetFirewallRule -Name "SatHunter-SSH-ZeroTier" -DisplayName "SSH from the ZeroTier lab network" -Direction Inbound -Protocol TCP -LocalPort 22 -RemoteAddress 10.147.18.0/24 -Action Allow -Profile Any | Out-Null
}
Restart-Service sshd
Ok "sshd running, port 22 open from 10.147.18.0/24, PowerShell shell"

# ---------------------------------------------------------------------------------------------
Step "3. Git and the repo"
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    winget install --id Git.Git -e --accept-source-agreements --accept-package-agreements --silent
    $env:Path += ";$env:ProgramFiles\Git\cmd"
}
$repoDir = Join-Path $Home_ "SatHunter-SDR"
if (-not (Test-Path (Join-Path $repoDir ".git"))) { git clone -q $Repo $repoDir }
git -C $repoDir fetch -q origin
git -C $repoDir checkout -q $Branch
git -C $repoDir pull -q origin $Branch
Ok "$repoDir on $Branch ($(git -C $repoDir log -1 --format=%h))"

# ---------------------------------------------------------------------------------------------
Step "4. radioconda (HackRF tools, Python)"
$py = Join-Path $Conda "python.exe"
if (-not (Test-Path $py)) {
    $rel = Invoke-RestMethod "https://api.github.com/repos/ryanvolz/radioconda/releases/latest" -Headers @{ "User-Agent" = "sathunter-setup" }
    $asset = $rel.assets | Where-Object { $_.name -match "Windows-x86_64\.exe$" } | Select-Object -First 1
    if (-not $asset) { throw "radioconda: no Windows installer in the latest release" }
    $exe = Join-Path $env:TEMP $asset.name
    Write-Host "   downloading $($asset.name) ($([math]::Round($asset.size / 1MB)) MB)..."
    Invoke-WebRequest $asset.browser_download_url -OutFile $exe -UseBasicParsing
    Start-Process $exe -ArgumentList "/InstallationType=JustMe", "/RegisterPython=0", "/AddToPath=0", "/S", "/D=$Conda" -Wait
}
if (-not (Test-Path $py)) { throw "radioconda did not install ($py missing)" }
& $py -c "import numpy, scipy, matplotlib; print('   numpy', numpy.__version__, 'scipy', scipy.__version__)"
# make hackrf_transfer and python findable in SSH sessions too (user PATH)
$add = "$Conda;$Conda\Library\bin;$Conda\Scripts"
$up = [Environment]::GetEnvironmentVariable("Path", "User")
if ($up -notlike "*$Conda\Library\bin*") { [Environment]::SetEnvironmentVariable("Path", "$add;$up", "User") }
$env:Path = "$add;$env:Path"
Ok "radioconda in $Conda (on the user PATH)"

# ---------------------------------------------------------------------------------------------
Step "5. Power: no sleep on mains"
powercfg /change standby-timeout-ac 0
powercfg /change hibernate-timeout-ac 0
powercfg /change monitor-timeout-ac 10
Ok "standby and hibernate off on AC (screen off after 10 min)"

# ---------------------------------------------------------------------------------------------
Step "6. HackRF driver"
$info = & (Join-Path $Conda "Library\bin\hackrf_info.exe") 2>&1 | Out-String
if ($info -notmatch "Serial number") {
    Warn "HackRF not seen (driver?). Plug it in; Zadig opens: Options > List All Devices, pick 'HackRF One',"
    Warn "driver WinUSB, Install Driver. Then press Enter here."
    $z = Join-Path $env:TEMP "zadig.exe"
    if (-not (Test-Path $z)) {
        $zr = Invoke-RestMethod "https://api.github.com/repos/pbatard/libwdi/releases/latest" -Headers @{ "User-Agent" = "sathunter-setup" }
        $za = $zr.assets | Where-Object { $_.name -match "^zadig-.*\.exe$" } | Select-Object -First 1
        Invoke-WebRequest $za.browser_download_url -OutFile $z -UseBasicParsing
    }
    Start-Process $z
    Read-Host "   Enter when the driver is installed"
    $info = & (Join-Path $Conda "Library\bin\hackrf_info.exe") 2>&1 | Out-String
}
Write-Host $info

# ---------------------------------------------------------------------------------------------
Step "Send this back"
Start-Sleep 3
$ztip = (Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue | Where-Object { $_.InterfaceAlias -match "ZeroTier" }).IPAddress
Write-Host "   user:         $env:USERNAME"
Write-Host "   computer:     $env:COMPUTERNAME"
Write-Host "   ZeroTier:     node $node, address $(if ($ztip) { $ztip } else { '(none yet: authorise the node on my.zerotier.com)' })"
Write-Host "   HackRF:       $(if ($info -match 'Serial number: (\S+)') { $Matches[1] } else { 'NOT FOUND' })"
Write-Host "   repo:         $repoDir ($Branch)"
