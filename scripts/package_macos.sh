#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="${VERSION:-0.1.0}"
APP_PATH="$ROOT_DIR/flutter_app/build/macos/Build/Products/Release/Quiz Machine.app"
RELEASE_DIR="$ROOT_DIR/release"

cd "$ROOT_DIR"
./scripts/build_backend.sh
(
  cd flutter_app
  if [[ ! -d macos ]]; then
    ./bootstrap.sh
  fi
  ./configure_platforms.sh
  ./enable_macos_network.sh
  flutter build macos --release
)

mkdir -p "$APP_PATH/Contents/Resources/backend" "$RELEASE_DIR"
cp dist/backend/quiz_backend "$APP_PATH/Contents/Resources/backend/quiz_backend"
cp dist/THIRD_PARTY_LICENSES.txt "$APP_PATH/Contents/Resources/THIRD_PARTY_LICENSES.txt"
cp LICENSE PRIVACY.md THIRD_PARTY_NOTICES.md "$APP_PATH/Contents/Resources/"
cp flutter_app/assets/fonts/DOTO-OFL.txt "$APP_PATH/Contents/Resources/"
chmod 755 "$APP_PATH/Contents/Resources/backend/quiz_backend"

if [[ -n "${MACOS_SIGN_IDENTITY:-}" ]]; then
  codesign --force --options runtime --timestamp \
    --sign "$MACOS_SIGN_IDENTITY" \
    "$APP_PATH/Contents/Resources/backend/quiz_backend"
  codesign --force --deep --options runtime --timestamp \
    --sign "$MACOS_SIGN_IDENTITY" "$APP_PATH"
else
  # Re-seal the bundle after adding the backend so local test builds remain
  # internally consistent. Public releases must use a Developer ID identity.
  codesign --force --deep --sign - "$APP_PATH"
fi

DMG_PATH="$RELEASE_DIR/Quiz-Machine-$VERSION-macOS.dmg"
rm -f "$DMG_PATH"
hdiutil create -volname "Quiz Machine" -srcfolder "$APP_PATH" \
  -ov -format UDZO "$DMG_PATH"

if [[ -n "${NOTARY_PROFILE:-}" ]]; then
  xcrun notarytool submit "$DMG_PATH" --keychain-profile "$NOTARY_PROFILE" --wait
  xcrun stapler staple "$DMG_PATH"
fi

shasum -a 256 "$DMG_PATH" > "$DMG_PATH.sha256"
printf 'Release created: %s\n' "$DMG_PATH"
