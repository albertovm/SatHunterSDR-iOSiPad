# Download SatNOGS observations (audio + demodulated frames) for decoder test vectors.
#   powershell -File tools/lab/satnogs_get.ps1 -ids 15383314,15388314 -out C:\Users\User\satnogs
param([string[]]$ids, [string]$out = "$env:USERPROFILE\satnogs")
$ProgressPreference = "SilentlyContinue"
$ids = $ids | ForEach-Object { $_ -split "," } | Where-Object { $_ }
foreach ($id in $ids) {
  $d = Join-Path $out $id; New-Item -ItemType Directory -Force $d | Out-Null
  $w = Invoke-WebRequest "https://network.satnogs.org/api/observations/?id=$id&format=json" -TimeoutSec 20 -UseBasicParsing
  $w.Content | Set-Content (Join-Path $d "obs.json")
  $o = ($w.Content | ConvertFrom-Json)[0]
  if ($o.payload) { Invoke-WebRequest $o.payload -OutFile (Join-Path $d "audio.ogg") -UseBasicParsing -TimeoutSec 120 }
  $k = 0
  foreach ($dd in $o.demoddata) { $k++; $u = $dd.payload_demod; Invoke-WebRequest $u -OutFile (Join-Path $d (Split-Path $u -Leaf)) -UseBasicParsing -TimeoutSec 30 }
  "$id $($o.norad_cat_id) $($o.transmitter_description) frames=$k " + (Get-ChildItem $d | Measure-Object Length -Sum).Sum
}
