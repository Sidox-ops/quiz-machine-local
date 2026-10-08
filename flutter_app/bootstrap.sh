#!/usr/bin/env bash
set -euo pipefail

if ! command -v flutter >/dev/null 2>&1; then
  echo "Flutter is not available in PATH."
  exit 1
fi

TMP_DIR="$(mktemp -d)"
cp pubspec.yaml "$TMP_DIR/pubspec.yaml"
cp analysis_options.yaml "$TMP_DIR/analysis_options.yaml"
cp lib/main.dart "$TMP_DIR/main.dart"

flutter create --project-name quiz_machine_local --platforms=macos,windows,linux .

cp "$TMP_DIR/pubspec.yaml" pubspec.yaml
cp "$TMP_DIR/analysis_options.yaml" analysis_options.yaml
cp "$TMP_DIR/main.dart" lib/main.dart
rm -rf "$TMP_DIR"

flutter pub get

./configure_platforms.sh

# Allow the sandboxed macOS Flutter app to call the local FastAPI backend.
./enable_macos_network.sh

echo "Flutter platform files generated. Try: flutter run -d macos"
