param(
    [string]$ApiBaseUrl = "https://67-205-160-8.sslip.io",
    [string]$ToolRoot = "",
    [string]$PublishedOutput = ""
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$projectRoot = Split-Path -Parent $PSScriptRoot
$codexRoot = if ($ToolRoot) {
    $ToolRoot
}
elseif ($env:AI_VISION_TOOL_ROOT) {
    $env:AI_VISION_TOOL_ROOT
}
else {
    Join-Path ([Environment]::GetFolderPath("MyDocuments")) "Codex"
}
$flutterRoot = Join-Path $codexRoot "flutter-sdk-3.44.8\flutter"
$androidSdk = if ($env:ANDROID_SDK_ROOT) {
    $env:ANDROID_SDK_ROOT
}
elseif ($env:ANDROID_HOME) {
    $env:ANDROID_HOME
}
else {
    Join-Path $codexRoot "android-sdk"
}
$sdkManager = Join-Path $androidSdk "cmdline-tools\latest\bin\sdkmanager.bat"
$flutterCommand = Get-Command flutter -ErrorAction SilentlyContinue
$flutter = if ($flutterCommand) {
    $flutterCommand.Source
}
else {
    Join-Path $flutterRoot "bin\flutter.bat"
}
$output = Join-Path $projectRoot "dist\android"
$publishedOutput = if ($PublishedOutput) {
    $PublishedOutput
}
else {
    Join-Path $projectRoot "dist\release"
}
$keyProperties = Join-Path $projectRoot "android\key.properties"
$keyStore = Join-Path $projectRoot "android\upload-keystore.jks"
$signingOutput = Join-Path $publishedOutput "signing"

function Invoke-NativeTool {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Executable,
        [Parameter()]
        [string[]]$Arguments = @(),
        [Parameter()]
        [string]$FailureMessage = "External tool failed."
    )

    # Java, sdkmanager, Gradle, and Flutter can write normal progress to
    # stderr. Windows PowerShell turns that into NativeCommandError when
    # ErrorActionPreference is Stop, so validate their exit codes directly.
    $previousPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    if ([System.IO.Path]::GetExtension($Executable) -ieq ".bat") {
        $argumentLine = ($Arguments | ForEach-Object {
            '"' + $_.Replace('"', '\"') + '"'
        }) -join " "
        $batchCommand = 'call "' + $Executable + '" ' + $argumentLine
        & $env:ComSpec /d /s /c $batchCommand 2>&1 |
            ForEach-Object { $_.ToString() } |
            Out-Host
    }
    else {
        & $Executable @Arguments 2>&1 |
            ForEach-Object { $_.ToString() } |
            Out-Host
    }
    $exitCode = $LASTEXITCODE
    $ErrorActionPreference = $previousPreference
    if ($exitCode -ne 0) {
        throw "$FailureMessage Exit code: $exitCode"
    }
}

function Invoke-FlutterTool {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments,
        [Parameter()]
        [string]$FailureMessage = "Flutter command failed."
    )

    $dart = Join-Path $flutterRoot "bin\cache\dart-sdk\bin\dart.exe"
    $snapshot = Join-Path $flutterRoot "bin\cache\flutter_tools.snapshot"
    $packageConfig = Join-Path $flutterRoot "packages\flutter_tools\.dart_tool\package_config.json"
    if (
        (Test-Path -LiteralPath $dart) -and
        (Test-Path -LiteralPath $snapshot) -and
        (Test-Path -LiteralPath $packageConfig)
    ) {
        Invoke-NativeTool `
            -Executable $dart `
            -Arguments (@("--packages=$packageConfig", $snapshot) + $Arguments) `
            -FailureMessage $FailureMessage
        return
    }

    Invoke-NativeTool `
        -Executable $flutter `
        -Arguments $Arguments `
        -FailureMessage $FailureMessage
}

function Find-JavaHome {
    $candidates = @(
        $env:JAVA_HOME,
        (Join-Path $codexRoot "android-studio\jbr"),
        "C:\Program Files\Android\Android Studio\jbr"
    ) | Where-Object { $_ }

    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath (Join-Path $candidate "bin\java.exe")) {
            return (Resolve-Path -LiteralPath $candidate).Path
        }
    }

    $downloads = Join-Path ([Environment]::GetFolderPath("UserProfile")) "Downloads"
    $downloadedStudio = Get-ChildItem -LiteralPath $downloads `
        -Filter "android-studio-quail2-patch1-windows*.zip" `
        -File -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1

    if ($downloadedStudio) {
        $expectedStudioHash = "4f98fee25f0b2a27ba40c1124df56b22f1790718352f17e09efbf9b5991d52f0"
        $actualStudioHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $downloadedStudio.FullName).Hash.ToLowerInvariant()
        if ($actualStudioHash -ne $expectedStudioHash) {
            throw "Portable Android Studio checksum mismatch. Expected $expectedStudioHash, received $actualStudioHash."
        }
        $studioRoot = Join-Path $codexRoot "android-studio"
        New-Item -ItemType Directory -Force -Path $studioRoot | Out-Null
        Expand-Archive -LiteralPath $downloadedStudio.FullName -DestinationPath $studioRoot -Force
        $java = Get-ChildItem -LiteralPath $studioRoot -Recurse -File -Filter "java.exe" |
            Where-Object { $_.FullName -like "*\jbr\bin\java.exe" } |
            Select-Object -First 1
        if ($java) {
            return (Split-Path -Parent (Split-Path -Parent $java.FullName))
        }
    }

    throw "Java 17+ was not found. Finish the portable Android Studio download or install a JDK, then rerun this script."
}

if (-not (Test-Path -LiteralPath $flutter)) {
    throw "Flutter SDK not found at $flutter"
}
if (-not (Test-Path -LiteralPath $sdkManager)) {
    throw "Android command-line SDK not found at $sdkManager"
}

$env:JAVA_HOME = Find-JavaHome
$env:ANDROID_HOME = $androidSdk
$env:ANDROID_SDK_ROOT = $androidSdk
$env:FLUTTER_ROOT = $flutterRoot
$flutterUserState = Join-Path $projectRoot ".flutter-user"
New-Item -ItemType Directory -Force -Path $flutterUserState | Out-Null
$env:APPDATA = $flutterUserState
$env:LOCALAPPDATA = $flutterUserState
$env:Path = "$env:JAVA_HOME\bin;$androidSdk\platform-tools;$env:Path"

# Flutter uses Git internally to determine its framework and engine versions.
# The portable SDK can be prepared by the Codex sandbox account and then built
# by the interactive Windows account. Trust only this SDK for this process;
# do not weaken the user's global Git safe-directory policy.
$gitConfigCountText = [Environment]::GetEnvironmentVariable("GIT_CONFIG_COUNT", "Process")
$gitConfigIndex = 0
if (-not [string]::IsNullOrWhiteSpace($gitConfigCountText)) {
    $parsedGitConfigCount = 0
    if ([int]::TryParse($gitConfigCountText, [ref]$parsedGitConfigCount)) {
        $gitConfigIndex = $parsedGitConfigCount
    }
}
$flutterSafeDirectory = (Resolve-Path -LiteralPath $flutterRoot).Path.Replace("\", "/")
[Environment]::SetEnvironmentVariable(
    "GIT_CONFIG_KEY_$gitConfigIndex",
    "safe.directory",
    "Process"
)
[Environment]::SetEnvironmentVariable(
    "GIT_CONFIG_VALUE_$gitConfigIndex",
    $flutterSafeDirectory,
    "Process"
)
$env:GIT_CONFIG_COUNT = [string]($gitConfigIndex + 1)

Write-Host "Java: $env:JAVA_HOME" -ForegroundColor Cyan
Write-Host "Android SDK: $androidSdk" -ForegroundColor Cyan
Write-Host "Flutter SDK trusted for this build process: $flutterSafeDirectory" -ForegroundColor Cyan

Invoke-NativeTool `
    -Executable (Join-Path $env:JAVA_HOME "bin\java.exe") `
    -Arguments @("-version") `
    -FailureMessage "Java validation failed."

if (-not (Test-Path -LiteralPath $keyProperties) -or -not (Test-Path -LiteralPath $keyStore)) {
    $passwordBytes = New-Object byte[] 24
    $random = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $random.GetBytes($passwordBytes)
    }
    finally {
        $random.Dispose()
    }
    $keyPassword = [Convert]::ToBase64String($passwordBytes)
    $keytool = Join-Path $env:JAVA_HOME "bin\keytool.exe"
    Invoke-NativeTool `
        -Executable $keytool `
        -Arguments @(
            "-genkeypair",
            "-v",
            "-keystore", $keyStore,
            "-storepass", $keyPassword,
            "-keypass", $keyPassword,
            "-alias", "upload",
            "-keyalg", "RSA",
            "-keysize", "2048",
            "-validity", "10000",
            "-dname", "CN=AI Vision, OU=Mobile, O=AI Vision, L=Tashkent, C=UZ"
        ) `
        -FailureMessage "Android upload-key generation failed."

    $keyStoreForGradle = $keyStore.Replace("\", "\\")
    @(
        "storePassword=$keyPassword",
        "keyPassword=$keyPassword",
        "keyAlias=upload",
        "storeFile=$keyStoreForGradle"
    ) | Set-Content -LiteralPath $keyProperties -Encoding ASCII
}

$androidPackagesReady = @(
    (Join-Path $androidSdk "platform-tools\adb.exe"),
    (Join-Path $androidSdk "platforms\android-36\android.jar"),
    (Join-Path $androidSdk "build-tools\36.0.0\aapt2.exe"),
    (Join-Path $androidSdk "ndk\28.2.13676358\source.properties")
) | ForEach-Object { Test-Path -LiteralPath $_ }

if ($androidPackagesReady -contains $false) {
    $licenseAnswers = (1..200 | ForEach-Object { "y" }) -join [Environment]::NewLine
    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    $licenseCommand = 'call "' + $sdkManager + '" "--licenses"'
    $licenseAnswers |
        & $env:ComSpec /d /s /c $licenseCommand 2>&1 |
        ForEach-Object { $_.ToString() } |
        Out-Host
    $licenseExitCode = $LASTEXITCODE
    $ErrorActionPreference = $previousErrorActionPreference
    if ($licenseExitCode -ne 0) {
        throw "Android SDK license acceptance failed. Exit code: $licenseExitCode"
    }

    Invoke-NativeTool `
        -Executable $sdkManager `
        -Arguments @(
            "platform-tools",
            "platforms;android-36",
            "build-tools;36.0.0",
            "ndk;28.2.13676358"
        ) `
        -FailureMessage "Android SDK package installation failed."
}
else {
    Write-Host "Android SDK packages are already installed; skipping package download." -ForegroundColor Green
}

Invoke-FlutterTool `
    -Arguments @("config", "--android-sdk", $androidSdk) `
    -FailureMessage "Flutter Android SDK configuration failed."

Set-Location $projectRoot
$offlinePackageConfig = Join-Path $projectRoot ".dart_tool\package_config.json"
$resolvedAllDependencies = $true
try {
    Invoke-FlutterTool `
        -Arguments @("pub", "get") `
        -FailureMessage "Flutter dependency resolution failed."
}
catch {
    if (-not (Test-Path -LiteralPath $offlinePackageConfig)) {
        throw
    }

    # The application itself has no third-party runtime packages. The project
    # carries a minimal package_config.json for release builds when pub.dev is
    # temporarily unreachable. Tests still require flutter_test and should be
    # run after network dependency resolution is available.
    $resolvedAllDependencies = $false
    Write-Warning "pub.dev is unavailable; continuing with the verified offline Flutter package configuration."
}

$analyzeArguments = if ($resolvedAllDependencies) {
    @("analyze", "--no-pub")
}
else {
    @("analyze", "--no-pub", "lib")
}
Invoke-FlutterTool `
    -Arguments $analyzeArguments `
    -FailureMessage "Flutter analysis failed."
Invoke-FlutterTool `
    -Arguments @(
        "build",
        "apk",
        "--debug",
        "--no-pub",
        "--dart-define=AI_VISION_API_BASE_URL=$ApiBaseUrl"
    ) `
    -FailureMessage "Debug APK build failed."
Invoke-FlutterTool `
    -Arguments @(
        "build",
        "apk",
        "--release",
        "--no-pub",
        "--dart-define=AI_VISION_API_BASE_URL=$ApiBaseUrl"
    ) `
    -FailureMessage "Release APK build failed."
Invoke-FlutterTool `
    -Arguments @(
        "build",
        "appbundle",
        "--release",
        "--no-pub",
        "--dart-define=AI_VISION_API_BASE_URL=$ApiBaseUrl"
    ) `
    -FailureMessage "Release AAB build failed."

New-Item -ItemType Directory -Force -Path $output, $publishedOutput, $signingOutput | Out-Null

$artifacts = @(
    @{
        Source = "build\app\outputs\flutter-apk\app-debug.apk"
        Name = "AI-Vision-debug.apk"
    },
    @{
        Source = "build\app\outputs\flutter-apk\app-release.apk"
        Name = "AI-Vision-release.apk"
    },
    @{
        Source = "build\app\outputs\bundle\release\app-release.aab"
        Name = "AI-Vision-release.aab"
    }
)

foreach ($artifact in $artifacts) {
    $source = Join-Path $projectRoot $artifact.Source
    if (-not (Test-Path -LiteralPath $source)) {
        throw "Expected build artifact was not created: $source"
    }
    Copy-Item -LiteralPath $source -Destination (Join-Path $output $artifact.Name) -Force
    Copy-Item -LiteralPath $source -Destination (Join-Path $publishedOutput $artifact.Name) -Force
}

Copy-Item -LiteralPath $keyStore -Destination (Join-Path $signingOutput "AI-Vision-upload-keystore.jks") -Force
Copy-Item -LiteralPath $keyProperties -Destination (Join-Path $signingOutput "key.properties") -Force
@(
    "AI Vision Android upload signing key",
    "",
    "Keep this directory private and back it up.",
    "Losing this key can prevent future Play Store updates.",
    "",
    "Keystore: AI-Vision-upload-keystore.jks",
    "Alias: upload",
    "Credentials: key.properties"
) | Set-Content -LiteralPath (Join-Path $signingOutput "README-PRIVATE.txt") -Encoding UTF8

Write-Host "Android artifacts:" -ForegroundColor Green
Get-ChildItem -LiteralPath $publishedOutput -File |
    Where-Object { $_.Extension -in ".apk", ".aab" } |
    ForEach-Object {
        [pscustomobject]@{
            Name = $_.Name
            Bytes = $_.Length
            SHA256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $_.FullName).Hash
        }
    } |
    Format-Table -AutoSize
