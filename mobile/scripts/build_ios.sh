#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_ROOT"

if ! command -v flutter >/dev/null 2>&1; then
  echo "Flutter 3.44+ is required." >&2
  exit 1
fi

if [[ ! -d ios ]]; then
  flutter create --platforms=android,ios --org=com.aivision --project-name=ai_vision_mobile .
fi

flutter pub get
flutter analyze
flutter test

API_BASE_URL="${AI_VISION_API_BASE_URL:-https://67-205-160-8.sslip.io}"
if [[ -z "${DEVELOPMENT_TEAM:-}" ]]; then
  echo "Set DEVELOPMENT_TEAM to the Apple Developer Team ID used for signing." >&2
  echo "Example: DEVELOPMENT_TEAM=ABCDE12345 ./scripts/build_ios.sh" >&2
  exit 2
fi

flutter build ios \
  --release \
  --no-codesign \
  --dart-define="AI_VISION_API_BASE_URL=$API_BASE_URL"

ARCHIVE_PATH="$PROJECT_ROOT/build/ios/archive/Runner.xcarchive"
EXPORT_PATH="$PROJECT_ROOT/build/ios/ipa"

xcodebuild \
  -workspace ios/Runner.xcworkspace \
  -scheme Runner \
  -configuration Release \
  -archivePath "$ARCHIVE_PATH" \
  -allowProvisioningUpdates \
  DEVELOPMENT_TEAM="$DEVELOPMENT_TEAM" \
  CODE_SIGN_STYLE=Automatic \
  archive

xcodebuild \
  -exportArchive \
  -archivePath "$ARCHIVE_PATH" \
  -exportPath "$EXPORT_PATH" \
  -exportOptionsPlist ios/ExportOptions.plist \
  -allowProvisioningUpdates

mkdir -p dist/ios
find "$EXPORT_PATH" -maxdepth 1 -name '*.ipa' -exec cp {} dist/ios/AI-Vision.ipa \;
echo "iOS artifact: dist/ios/AI-Vision.ipa"
