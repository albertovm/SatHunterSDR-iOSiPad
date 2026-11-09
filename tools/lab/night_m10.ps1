# Unattended HackRF night batch for the M10 build (v0.2.0-beta12) on the home lab PC.
# hackrf_server.py (env hackrf2026) must be running. Chain: HackRF -> 30+30+10 dB -> 1 m coax ->
# Spacewalker LNA -> RTL-SDR V3 -> phone. Levels at the LNA input (--atten 72.8, from the BB60C calibration of 2026-11-09).
#   1. 9k6 G3RUH, release build: 1 dB steps, NFM 20 and 25 kHz, 30 s per level
#   2. 9k6 G3RUH deviation 2 kHz and 4.5 kHz (satellites differ), NFM 20 kHz
#   3. APRS 3 kHz deviation regression on beta12
#   4. CW decoder vs Doppler ramp (0 ... 100 Hz/s)
#   5. Two-tone in-band IIP3 (HackRF's own IM3 sets a floor: read it as an upper bound)
#   6. Drift HackRF vs RTL for the rest of the night
$ErrorActionPreference = "Continue"
$py = "C:\Users\User\radioconda\python.exe"
$ip = "192.168.1.237"
Set-Location C:\Users\User\SatHunter-SDR
$log = "C:\Users\User\night_m10.log"
$common = @("--gen", "hackrf", "--phone", $ip, "--pin", "1027", "--atten", "72.8")
function Run($what, $args_) {
    "== $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') $what" | Add-Content $log
    & $py -u @args_ 2>&1 | Add-Content $log
}
$g3 = "--g3ruh-levels=-104,-106,-108,-109,-110,-111,-112,-113,-114,-115,-116,-117,-118,-119,-120"
Run "G3RUH 3 kHz dev" (@("tools\lab\rx_extra.py") + $common + @("--part", "g3ruh", $g3, "--g3ruh-bws", "20000,25000", "--g3ruh-secs", "30", "--name", "g3ruh-beta12"))
Run "G3RUH 2 kHz dev" (@("tools\lab\rx_extra.py") + $common + @("--part", "g3ruh", $g3, "--g3ruh-dev", "2000", "--g3ruh-bws", "20000", "--g3ruh-secs", "30", "--name", "g3ruh-beta12-dev2k"))
Run "G3RUH 4.5 kHz dev" (@("tools\lab\rx_extra.py") + $common + @("--part", "g3ruh", $g3, "--g3ruh-dev", "4500", "--g3ruh-bws", "20000,25000", "--g3ruh-secs", "30", "--name", "g3ruh-beta12-dev4k5"))
Run "APRS 3 kHz dev" (@("tools\lab\rx_extra.py") + $common + @("--part", "aprs", "--aprs-dev", "3000", "--aprs-bws", "12500", "--aprs-levels=-110,-115,-117,-118,-119,-120,-121,-122,-124,-126", "--name", "aprs-beta12"))
Run "CW Doppler" (@("tools\lab\rx_extra.py") + $common + @("--part", "doppler", "--rates", "0,10,25,50,100,200", "--cw-levels=-130,-135,-138", "--name", "doppler-hackrf"))
Run "Two-tone" (@("tools\lab\rx_extra.py") + $common + @("--part", "twotone", "--name", "twotone-hackrf"))
Run "Drift" (@("tools\lab\drift.py") + $common + @("--level", "-100", "--mins", "240", "--every", "30", "--name", "drift-hackrf-night2"))
"== $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') done" | Add-Content $log
