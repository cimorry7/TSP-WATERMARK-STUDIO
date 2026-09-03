$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSCommandPath
$html = Join-Path $root 'watermark-smart.html'
if (-not (Test-Path -LiteralPath $html)) {
    [System.Windows.Forms.MessageBox]::Show("File aplikasi tidak ditemukan:`n$html", 'Smart Watermark Studio')
    exit 1
}

$browserCandidates = @(
    "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
    "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe",
    "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe",
    "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe",
    "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe"
)
$browser = $browserCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
$url = ([System.Uri]((Resolve-Path -LiteralPath $html).Path)).AbsoluteUri
if ($browser) {
    Start-Process -FilePath $browser -ArgumentList "--app=$url"
} else {
    Start-Process -FilePath $html
}
