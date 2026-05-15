param(
    [string]$TaskName = "AlphaLensWorkers",
    [string]$RepoRoot = (Get-Location).Path
)

$batPath = Join-Path $RepoRoot "run_alpha_lens_workers.bat"
if (-not (Test-Path $batPath)) {
    throw "Batch file not found: $batPath"
}

$startupDir = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\Startup"
if (-not (Test-Path $startupDir)) {
    New-Item -Path $startupDir -ItemType Directory | Out-Null
}

$shortcutPath = Join-Path $startupDir "$TaskName.lnk"
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $batPath
$shortcut.WorkingDirectory = $RepoRoot
$shortcut.WindowStyle = 1
$shortcut.Description = "Alpha Lens background workers startup shortcut"
$shortcut.Save()

Write-Output "Created startup shortcut at: $shortcutPath"
Write-Output "Alpha Lens worker process will start automatically at login."
