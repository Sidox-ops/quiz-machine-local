#!/usr/bin/env bash
set -euo pipefail

# Flutter macOS apps run sandboxed. Without this entitlement, HTTP calls to the
# local FastAPI backend can fail with: "Operation not permitted (errno = 1)".
if [[ "$(uname -s)" != "Darwin" ]]; then
  exit 0
fi

for file in macos/Runner/DebugProfile.entitlements macos/Runner/Release.entitlements; do
  if [[ ! -f "$file" ]]; then
    continue
  fi

  for entitlement in com.apple.security.network.client com.apple.security.network.server; do
    if /usr/libexec/PlistBuddy -c "Print :$entitlement" "$file" 2>/dev/null | grep -q "true"; then
      continue
    fi

    /usr/libexec/PlistBuddy -c "Delete :$entitlement" "$file" >/dev/null 2>&1 || true
    /usr/libexec/PlistBuddy -c "Add :$entitlement bool true" "$file"
  done
done

XCSETTINGS="macos/Runner/Configs/AppInfo.xcconfig"
if [[ -f "$XCSETTINGS" ]]; then
  if ! grep -q "CODE_SIGN_ALLOW_ENTITLEMENTS_MODIFICATION" "$XCSETTINGS"; then
    echo "CODE_SIGN_ALLOW_ENTITLEMENTS_MODIFICATION = YES" >> "$XCSETTINGS"
  fi
fi

echo "macOS loopback client/server entitlements enabled."
