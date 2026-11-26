$out = Join-Path $PSScriptRoot 'audio'
New-Item -ItemType Directory -Path $out -Force | Out-Null
Add-Type -AssemblyName System.Speech
$scriptLines = Get-Content -Raw -Encoding UTF8 -LiteralPath (Join-Path $PSScriptRoot 'narration.json') | ConvertFrom-Json
foreach ($line in $scriptLines) {
    $voice = New-Object System.Speech.Synthesis.SpeechSynthesizer
    $voice.SelectVoice('Microsoft Zira Desktop')
    $voice.Rate = 0
    $voice.SetOutputToWaveFile((Join-Path $out ($line[0] + '.wav')))
    $voice.Speak($line[1])
    $voice.Dispose()
}
