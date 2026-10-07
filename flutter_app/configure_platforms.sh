#!/usr/bin/env bash
set -euo pipefail

replace_text() {
  local file="$1"
  local before="$2"
  local after="$3"
  [[ -f "$file" ]] || return 0
  perl -0pi -e "s/\Q$before\E/$after/g" "$file"
}

replace_text macos/Runner/Configs/AppInfo.xcconfig \
  "PRODUCT_NAME = ai103_quiz_ui" \
  "PRODUCT_NAME = Quiz Machine"
replace_text macos/Runner/Configs/AppInfo.xcconfig \
  "PRODUCT_BUNDLE_IDENTIFIER = com.example.ai103QuizUi" \
  "PRODUCT_BUNDLE_IDENTIFIER = app.quizmachine.desktop"
replace_text macos/Runner/Configs/AppInfo.xcconfig \
  "PRODUCT_COPYRIGHT = Copyright © 2026 com.example. All rights reserved." \
  "PRODUCT_COPYRIGHT = Copyright (C) 2026 Quiz Machine publisher. All rights reserved."

replace_text windows/runner/Runner.rc '"com.example"' '"Quiz Machine publisher"'
replace_text windows/runner/Runner.rc '"ai103_quiz_ui"' '"Quiz Machine"'
replace_text windows/runner/Runner.rc \
  'Copyright (C) 2026 com.example. All rights reserved.' \
  'Copyright (C) 2026 Quiz Machine publisher. All rights reserved.'
replace_text windows/runner/main.cpp 'L"ai103_quiz_ui"' 'L"Quiz Machine"'

echo "Desktop platform metadata configured."
