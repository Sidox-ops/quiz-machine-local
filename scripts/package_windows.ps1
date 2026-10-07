$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Version = if ($env:VERSION) { $env:VERSION } else { "0.1.0" }
$Release = Join-Path $Root "release"
$Python = if ($env:PYTHON) { $env:PYTHON } else { Join-Path $Root ".venv\Scripts\python.exe" }

Set-Location $Root
if (Test-Path dist\backend) { Remove-Item -Recurse -Force dist\backend }
if (Test-Path build-backend) { Remove-Item -Recurse -Force build-backend }
& $Python -m PyInstaller --distpath dist\backend --workpath build-backend --clean --noconfirm packaging\quiz_backend.spec
& $Python -m piplicenses --format=plain-vertical --with-license-file --output-file=dist\THIRD_PARTY_LICENSES.txt

Set-Location (Join-Path $Root "flutter_app")
if (-not (Test-Path windows)) { bash .\bootstrap.sh }
bash .\configure_platforms.sh
flutter build windows --release

$Bundle = Join-Path $Root "flutter_app\build\windows\x64\runner\Release"
$Backend = Join-Path $Bundle "backend"
New-Item -ItemType Directory -Force -Path $Backend, $Release | Out-Null
Copy-Item (Join-Path $Root "dist\backend\quiz_backend.exe") $Backend
Copy-Item (Join-Path $Root "dist\THIRD_PARTY_LICENSES.txt") $Bundle
Copy-Item (Join-Path $Root "LICENSE"), (Join-Path $Root "PRIVACY.md"), (Join-Path $Root "THIRD_PARTY_NOTICES.md") $Bundle
Copy-Item (Join-Path $Root "flutter_app\assets\fonts\DOTO-OFL.txt") $Bundle

$Zip = Join-Path $Release "Quiz-Machine-$Version-Windows-x64.zip"
if (Test-Path $Zip) { Remove-Item $Zip }
Compress-Archive -Path "$Bundle\*" -DestinationPath $Zip
Get-FileHash -Algorithm SHA256 $Zip | ForEach-Object { "$($_.Hash.ToLower())  $([IO.Path]::GetFileName($Zip))" } | Set-Content "$Zip.sha256"
Write-Host "Release created: $Zip"
