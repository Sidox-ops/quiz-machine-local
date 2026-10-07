import 'package:ai103_quiz_ui/app/quiz_app.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'fakes/fake_quiz_repository.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  tearDown(() {
    TestWidgetsFlutterBinding.instance.platformDispatcher.clearAllTestValues();
  });

  testWidgets('mobile setup layout', (tester) async {
    tester.view.devicePixelRatio = 1;
    tester.view.physicalSize = const Size(390, 844);

    await tester.pumpWidget(
      Ai103QuizApp(repository: FakeQuizRepository()),
    );
    await tester.pumpAndSettle();

    await expectLater(
      find.byType(Scaffold),
      matchesGoldenFile('goldens/setup_mobile.png'),
    );
  });

  testWidgets('desktop question layout', (tester) async {
    tester.view.devicePixelRatio = 1;
    tester.view.physicalSize = const Size(1440, 900);

    await tester.pumpWidget(
      Ai103QuizApp(repository: FakeQuizRepository()),
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
  });
}
