$ErrorActionPreference = "Stop"

$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$flutterRoot = "C:\Users\Porter\Documents\Codex\flutter-sdk-3.44.8\flutter"
$templateRoot = Join-Path $flutterRoot "packages\flutter_tools\templates\app"

if (-not (Test-Path -LiteralPath $templateRoot)) {
    throw "Flutter templates were not found at $templateRoot"
}

$values = @{
    projectName = "ai_vision_mobile"
    titleCaseProjectName = "AI Vision"
    androidIdentifier = "com.aivision.ai_vision_mobile"
    iosIdentifier = "com.aivision.aiVisionMobile"
    gradleVersion = "9.1.0"
    agpVersion = "9.0.1"
    kotlinVersion = "2.3.20"
    androidSdkVersion = "36"
    pluginProjectName = "ai_vision_mobile"
    pluginClass = "AiVisionMobilePlugin"
    iosDevelopmentTeam = ""
}

function Render-TemplateText {
    param([string]$Text)

    # Optional template sections used by plugin projects are disabled here.
    $Text = [regex]::Replace(
        $Text,
        '(?s)\{\{#hasIosDevelopmentTeam\}\}.*?\{\{/hasIosDevelopmentTeam\}\}',
        ''
    )
    $Text = [regex]::Replace(
        $Text,
        '(?s)\{\{#withSwiftPackageManager\}\}.*?\{\{/withSwiftPackageManager\}\}',
        ''
    )
    $Text = [regex]::Replace(
        $Text,
        '(?s)\{\{#withPlatformChannelPluginHook\}\}.*?\{\{/withPlatformChannelPluginHook\}\}',
        ''
    )
    $Text = [regex]::Replace(
        $Text,
        '(?s)\{\{\^withPlatformChannelPluginHook\}\}(.*?)\{\{/withPlatformChannelPluginHook\}\}',
        '$1'
    )

    foreach ($entry in $values.GetEnumerator()) {
        $Text = $Text.Replace("{{" + $entry.Key + "}}", [string]$entry.Value)
    }
    return $Text
}

function Expand-TemplateTree {
    param(
        [string]$Source,
        [string]$Destination
    )

    foreach ($file in Get-ChildItem -LiteralPath $Source -Recurse -File) {
        $relative = $file.FullName.Substring($Source.Length).TrimStart("\")
        $relative = $relative.Replace(
            "androidIdentifier",
            "com\aivision\ai_vision_mobile"
        )
        $binarySuffix = if ($relative.EndsWith(".copy.tmpl")) {
            ".copy.tmpl"
        } elseif ($relative.EndsWith(".img.tmpl")) {
            ".img.tmpl"
        } else {
            $null
        }
        if ($null -ne $binarySuffix) {
            $relative = $relative.Substring(0, $relative.Length - $binarySuffix.Length)
            $target = Join-Path $Destination $relative
            New-Item -ItemType Directory -Force -Path (Split-Path -Parent $target) | Out-Null
            Copy-Item -LiteralPath $file.FullName -Destination $target -Force
            continue
        }
        if ($relative.EndsWith(".tmpl")) {
            $relative = $relative.Substring(0, $relative.Length - ".tmpl".Length)
        }

        $target = Join-Path $Destination $relative
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $target) | Out-Null
        $content = Get-Content -LiteralPath $file.FullName -Raw
        $rendered = Render-TemplateText -Text $content
        [System.IO.File]::WriteAllText(
            $target,
            $rendered,
            [System.Text.UTF8Encoding]::new($false)
        )
    }
}

$androidTarget = Join-Path $projectRoot "android"
$iosTarget = Join-Path $projectRoot "ios"

if (-not (Test-Path -LiteralPath $androidTarget)) {
    New-Item -ItemType Directory -Path $androidTarget | Out-Null
    Expand-TemplateTree `
        -Source (Join-Path $templateRoot "android.tmpl") `
        -Destination $androidTarget
    Expand-TemplateTree `
        -Source (Join-Path $templateRoot "android-kotlin.tmpl") `
        -Destination $androidTarget
}
$gradleWrapperSource = Join-Path $flutterRoot "bin\cache\artifacts\gradle_wrapper"
Copy-Item `
    -LiteralPath (Join-Path $gradleWrapperSource "gradlew") `
    -Destination (Join-Path $androidTarget "gradlew") `
    -Force
Copy-Item `
    -LiteralPath (Join-Path $gradleWrapperSource "gradlew.bat") `
    -Destination (Join-Path $androidTarget "gradlew.bat") `
    -Force
New-Item `
    -ItemType Directory `
    -Force `
    -Path (Join-Path $androidTarget "gradle\wrapper") | Out-Null
Copy-Item `
    -LiteralPath (Join-Path $gradleWrapperSource "gradle\wrapper\gradle-wrapper.jar") `
    -Destination (Join-Path $androidTarget "gradle\wrapper\gradle-wrapper.jar") `
    -Force

if (-not (Test-Path -LiteralPath $iosTarget)) {
    New-Item -ItemType Directory -Path $iosTarget | Out-Null
    Expand-TemplateTree `
        -Source (Join-Path $templateRoot "ios.tmpl") `
        -Destination $iosTarget
}

# Repair binary iOS assets if this script is rerun after an interrupted render.
$iosTemplate = Join-Path $templateRoot "ios.tmpl"
foreach ($file in Get-ChildItem -LiteralPath $iosTemplate -Recurse -File -Filter "*.img.tmpl") {
    $relative = $file.FullName.Substring($iosTemplate.Length).TrimStart("\")
    $relative = $relative.Substring(0, $relative.Length - ".img.tmpl".Length)
    $target = Join-Path $iosTarget $relative
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $target) | Out-Null
    Copy-Item -LiteralPath $file.FullName -Destination $target -Force
}
foreach ($stale in Get-ChildItem -LiteralPath $iosTarget -Recurse -File -Filter "*.png.img") {
    Remove-Item -LiteralPath $stale.FullName -Force
}
$moduleIosAssets = Join-Path $templateRoot "..\module\ios\host_app_ephemeral\Runner.tmpl\Assets.xcassets"
Copy-Item `
    -Path (Join-Path $moduleIosAssets "AppIcon.appiconset\*.png") `
    -Destination (Join-Path $iosTarget "Runner\Assets.xcassets\AppIcon.appiconset") `
    -Force
Copy-Item `
    -Path (Join-Path $moduleIosAssets "LaunchImage.imageset\*.png") `
    -Destination (Join-Path $iosTarget "Runner\Assets.xcassets\LaunchImage.imageset") `
    -Force

$manifest = Join-Path $androidTarget "app\src\main\AndroidManifest.xml"
$manifestText = Get-Content -LiteralPath $manifest -Raw
$manifestText = $manifestText.Replace('android:label="ai_vision_mobile"', 'android:label="AI Vision"')
[System.IO.File]::WriteAllText(
    $manifest,
    $manifestText,
    [System.Text.UTF8Encoding]::new($false)
)

Write-Host "Native projects generated:" -ForegroundColor Green
Write-Host "  $androidTarget"
Write-Host "  $iosTarget"
