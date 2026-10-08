import 'package:quiz_machine_local/app/quiz_app.dart';
import 'package:quiz_machine_local/core/design_system/theme/app_theme.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';

import 'fakes/fake_quiz_repository.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUpAll(() async {
    final fontBytes = rootBundle.load('assets/fonts/Doto.ttf');
    final brandFont = FontLoader('Doto')..addFont(fontBytes);
    await brandFont.load();
  });

  tearDown(() {
    TestWidgetsFlutterBinding.instance.platformDispatcher.clearAllTestValues();
  });

  testWidgets('mobile setup layout', (tester) async {
    tester.view.devicePixelRatio = 1;
    tester.view.physicalSize = const Size(390, 844);

    await tester.pumpWidget(
      QuizMachineApp(
        repository: FakeQuizRepository(),
        theme: _previewTheme(),
      ),
    );
    await tester.pumpAndSettle();

    await expectLater(
      find.byType(Scaffold),
      matchesGoldenFile('goldens/setup_mobile.png'),
    );
  }, tags: 'golden');

  testWidgets('desktop question layout', (tester) async {
    tester.view.devicePixelRatio = 1;
    tester.view.physicalSize = const Size(1440, 900);

    await tester.pumpWidget(
      QuizMachineApp(
        repository: FakeQuizRepository(),
        theme: _previewTheme(),
      ),
    );
    await tester.pumpAndSettle();

    final startButton = find.widgetWithText(FilledButton, 'Start session');
    await tester.ensureVisible(startButton);
    await tester.tap(startButton);
    await tester.pumpAndSettle();

    await expectLater(
      find.byType(Scaffold),
      matchesGoldenFile('goldens/question_desktop.png'),
    );
  }, tags: 'golden');
}

ThemeData _previewTheme() {
  final base = AppTheme.light;
  return base.copyWith(
    textTheme: base.textTheme.apply(fontFamily: 'Doto'),
    primaryTextTheme: base.primaryTextTheme.apply(fontFamily: 'Doto'),
  );
}
