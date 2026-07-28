# AI Vision Mobile

Cross-platform Flutter application for Android and iOS, based on the approved
AI Vision mobile design.

## Included

- Dark industrial theme and clean light theme with one global toggle
- Splash, onboarding, login, dashboard, live cameras, alerts, machines,
  analytics, violations, reports, notifications, profile, settings, and drawer
- Responsive phone, tablet, portrait, and landscape layouts
- Head Admin, Factory Admin, and Operator navigation driven by the authenticated
  backend account
- Production backend authentication through `/api/v2/auth/login`
- Live status and registered cameras loaded from `/api/status` and `/api/cameras`
- Active camera frames loaded from the Stream Manager-backed `/api/live_frame`
- Production server default: `https://67-205-160-8.sslip.io`
- No third-party runtime dependencies

## Build

On Windows with Flutter and Android Studio installed:

```powershell
.\scripts\build_android.ps1
```

To target a different backend:

```powershell
.\scripts\build_android.ps1 -ApiBaseUrl "https://staging.example.com"
```

The first Android build generates a private upload key. Back up
`outputs/mobile/signing`; it is required for future Google Play updates and is
intentionally excluded from Git.

GitHub Actions also builds all three Android artifacts. For Play-signed CI
releases, configure repository secrets `ANDROID_KEYSTORE_BASE64`,
`ANDROID_STORE_PASSWORD`, `ANDROID_KEY_PASSWORD`, and `ANDROID_KEY_ALIAS`.
Without those secrets, CI artifacts use the development signing fallback.

On macOS with Flutter, Xcode, CocoaPods, and Apple signing configured:

```bash
DEVELOPMENT_TEAM=ABCDE12345 ./scripts/build_ios.sh
```

Android outputs are copied to `dist/android`. The iOS archive is copied to
`dist/ios` when an Apple Developer certificate and provisioning profile are
available.
