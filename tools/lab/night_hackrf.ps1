# Unattended HackRF night batch on the home lab PC (hackrf_server.py must be running).
# Chain: HackRF -> 30+30+10 dB -> 1 m coax -> Spacewalker LNA -> RTL-SDR (phone). Levels at the LNA input.
$ErrorActionPreference = "Continue"
$py = "C:\Users\User\radioconda\python.exe"
$ip = "192.168.1.237"
Set-Location C:\Users\User\SatHunter-SDR
$log = "C:\Users\User\night.log"
function Run($what, $args_) {
    "== $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') $what" | Add-Content $log
    & $py -u @args_ 2>&1 | Add-Content $log
}
Run "APRS 3 kHz deviation" @("tools\lab\rx_extra.py", "--gen", "hackrf", "--phone", $ip, "--pin", "1027", "--atten", "70.5", "--part", "aprs", "--aprs-dev", "3000", "--aprs-bws", "12500,6000", "--aprs-levels=-105,-115,-118,-120,-122,-124,-126,-128,-130", "--name", "aprs-hackrf-3k")
Run "APRS 1 kHz deviation" @("tools\lab\rx_extra.py", "--gen", "hackrf", "--phone", $ip, "--pin", "1027", "--atten", "70.5", "--part", "aprs", "--aprs-dev", "1000", "--aprs-bws", "12500,6000", "--aprs-levels=-105,-115,-118,-120,-122,-124,-126,-128,-130", "--name", "aprs-hackrf-1k")
Run "SSTV Robot 36 limit" @("tools\lab\sstv_test.py", "--gen", "hackrf", "--phone", $ip, "--pin", "1027", "--atten", "70.5", "--mode", "robot36", "--levels=-120,-128,-132,-134,-136,-138", "--name", "sstv-hackrf-robot36")
"== $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') done" | Add-Content $log
