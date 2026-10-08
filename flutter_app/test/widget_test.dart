import 'package:quiz_machine_local/app/quiz_app.dart';
import 'package:quiz_machine_local/core/runtime/local_backend_manager.dart';
import 'package:quiz_machine_local/features/quiz/domain/quiz_models.dart';
import 'package:quiz_machine_local/features/quiz/presentation/organisms/generation_panel.dart';
import 'package:quiz_machine_local/features/quiz/presentation/pages/quiz_page.dart';
import 'package:quiz_machine_local/features/setup/domain/setup_models.dart';
import 'package:quiz_machine_local/features/setup/presentation/corpus_import_dialog.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'fakes/fake_quiz_repository.dart';
import 'fakes/fake_environment_repository.dart';

class _NeverAcceptedStore extends AcceptanceStore {
  @override
  bool isAccepted() => false;

  @override
  void accept() {}
}

class _ShuffledAnswerRepository extends FakeQuizRepository {
  @override
  Future<QuizAnswerResult> submitAnswer(
    String questionId,
    String option, {
    double? elapsedSeconds,
  }) async {
    return const QuizAnswerResult(
      correct: false,
      selectedOptionId: 'opt_1',
      correctOptionId: 'opt_4',
      explanation: 'A longer system prompt is correct. Frozen explanation.',
      optionExplanations: [
        OptionExplanation(optionId: 'opt_1', explanation: 'First rationale.'),
        OptionExplanation(optionId: 'opt_2', explanation: 'Second rationale.'),
        OptionExplanation(optionId: 'opt_3', explanation: 'Third rationale.'),
        OptionExplanation(optionId: 'opt_4', explanation: 'Fourth rationale.'),
      ],
      progress: QuizProgress(asked: 1, correct: 0, accuracy: 0),
      decisiveClue: 'The workload needs a repeatable evaluation baseline.',
      learningRule: 'Match the explicit requirement before comparing services.',
      selectedOptionFeedback: 'The selected capability solves another problem.',
      takeaway: 'Requirement first, capability second.',
    );
  }
}

class _DashboardRepository extends FakeQuizRepository {
  ProgressResetScope? resetScope;

  @override
  Future<QuizProgress> loadProgress({String? certificationCode}) async {
    return const QuizProgress(
      asked: 12,
      correct: 8,
      accuracy: 2 / 3,
      recentAccuracy: 0.75,
      averageSeconds: 31,
      recentAttemptCount: 12,
      domains: [
        ProgressMetric(
          label: 'Plan an Azure AI solution',
          asked: 12,
          correct: 8,
          accuracy: 2 / 3,
          mastery: 0.64,
        ),
      ],
      objectives: [
        ProgressMetric(
          label: 'Choose a grounded retrieval strategy',
          asked: 4,
          correct: 2,
          accuracy: 0.5,
          mastery: 0.5,
        ),
      ],
      confusions: [
        ProgressConfusion(
          learningObjective: 'Choose a grounded retrieval strategy',
          selectedOptionText: 'Use model memory',
          correctOptionText: 'Retrieve approved evidence',
          count: 2,
        ),
      ],
    );
  }

  @override
  Future<QuizProgress> resetProgress({
    required ProgressResetScope scope,
    String? certificationCode,
  }) async {
    resetScope = scope;
    return QuizProgress.empty;
  }
}

class _ModelEnvironmentRepository extends FakeEnvironmentRepository {
  String selectedModel = 'llama3.2:3b';

  SystemDiagnostics get _diagnostics => SystemDiagnostics(
        platform: 'macOS',
        architecture: 'arm64',
        ollamaInstalled: true,
        ollamaReachable: true,
        llmModel: selectedModel,
        llmReady: true,
        embeddingModel: 'nomic-embed-text',
        embeddingReady: true,
        indexReady: true,
        indexedChunks: 33,
        knowledgeProvider: 'microsoft_learn_mcp',
        knowledgeReady: true,
        knowledgeCheckCompleted: true,
        freeDiskBytes: 20 * 1024 * 1024 * 1024,
        recommendedFreeBytes: 8 * 1024 * 1024 * 1024,
        diskReady: true,
        recommendedLlmModel: 'qwen3:8b',
        ollamaModels: [
          LocalModelInfo(
            name: 'llama3.2:3b',
            size: 2 * 1024 * 1024 * 1024,
            parameterSize: '3B',
            compatible: true,
            compatibilityReason: 'Compatible local chat model.',
            selected: selectedModel == 'llama3.2:3b',
          ),
          LocalModelInfo(
            name: 'qwen3:8b',
            size: 5 * 1024 * 1024 * 1024,
            parameterSize: '8B',
            compatible: true,
            compatibilityReason: 'Compatible local chat model.',
            selected: selectedModel == 'qwen3:8b',
            recommended: true,
          ),
        ],
      );

  @override
  Future<SystemDiagnostics> diagnostics() async => _diagnostics;

  @override
  Future<SystemDiagnostics> selectModel(String model) async {
    selectedModel = model;
    return _diagnostics;
  }
}

void main() {
  testWidgets('shows durable generation progress and retry count', (
    tester,
  ) async {
    var cancelled = false;
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: GenerationPanel(
            completed: 7,
            total: 30,
            attempts: 12,
            rejected: 5,
            phase: 'generating_questions',
            corpusCompleted: 0,
            corpusTotal: 0,
            corpusAttempts: 0,
            corpusRetries: 0,
            message:
                'Question 8 of 30: candidate rejected; retrying automatically.',
            cancelling: false,
            onCancel: () => cancelled = true,
          ),
        ),
      ),
    );

    expect(find.text('7 of 30'), findsOneWidget);
    expect(
      find.text(
        '0 reused from the validated bank • '
        '12 candidates checked • 5 rejected and retried',
      ),
      findsOneWidget,
    );
    expect(
      find.textContaining('Revision never waits for a model call'),
      findsOneWidget,
    );
    await tester.tap(find.text('Cancel generation'));
    expect(cancelled, isTrue);
  });

  testWidgets('shows certification corpus preparation progress', (
    tester,
  ) async {
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: GenerationPanel(
            completed: 0,
            total: 30,
            attempts: 0,
            rejected: 0,
            phase: 'preparing_corpus',
            corpusCompleted: 12,
            corpusTotal: 27,
            corpusAttempts: 2,
            corpusRetries: 1,
            message: 'Preparing corpus objective 13 of 27...',
            cancelling: false,
            onCancel: () {},
          ),
        ),
      ),
    );

    expect(find.text('Preparing certification corpus'), findsOneWidget);
    expect(find.text('12 of 27 objectives'), findsOneWidget);
    expect(find.text('2 preparation attempt(s) • 1 retried'), findsOneWidget);
    expect(find.textContaining('small evidence packet'), findsOneWidget);
  });

  testWidgets('changes the installed Ollama model from the quiz workspace', (
    tester,
  ) async {
    final environment = _ModelEnvironmentRepository();
    await tester.pumpWidget(
      MaterialApp(
        home: QuizPage(
          repository: FakeQuizRepository(),
          environmentRepository: environment,
          themeMode: ThemeMode.light,
          onThemeModeChanged: (_) {},
        ),
      ),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.byTooltip('Local model'));
    await tester.pumpAndSettle();

    expect(find.text('Local Ollama model'), findsOneWidget);
    expect(find.textContaining('never downloads'), findsOneWidget);

    await tester.tap(find.byType(DropdownButtonFormField<String>));
    await tester.pumpAndSettle();
    await tester.tap(find.text('qwen3:8b (recommended)').last);
    await tester.pumpAndSettle();
    await tester.tap(find.widgetWithText(FilledButton, 'Test and use model'));
    await tester.pumpAndSettle();

    expect(environment.selectedModel, 'qwen3:8b');
    expect(
      find.text('qwen3:8b will be used for future question generation.'),
      findsOneWidget,
    );
  });

  testWidgets('shows structured Markdown drag-and-drop import', (tester) async {
    await tester.pumpWidget(
      MaterialApp(
        home: Builder(
          builder: (context) => Scaffold(
            body: FilledButton(
              onPressed: () =>
                  CorpusImportDialog.show(context, FakeEnvironmentRepository()),
              child: const Text('Open importer'),
            ),
          ),
        ),
      ),
    );

    await tester.tap(find.text('Open importer'));
    await tester.pumpAndSettle();

    expect(find.text('Import Markdown corpora'), findsOneWidget);
    expect(find.text('Drop Markdown files here'), findsOneWidget);
    expect(find.text('View required Markdown format'), findsOneWidget);
    expect(
      tester
          .widget<FilledButton>(
            find.widgetWithText(FilledButton, 'Import valid files'),
          )
          .onPressed,
      isNull,
    );
  });

  testWidgets('requires licence acknowledgement before system setup', (
    tester,
  ) async {
    await tester.pumpWidget(
      QuizMachineApp(
        repository: FakeQuizRepository(),
        environmentRepository: FakeEnvironmentRepository(),
        acceptanceStore: _NeverAcceptedStore(),
      ),
    );

    expect(find.text('Before you begin'), findsOneWidget);
    expect(find.text('Continue'), findsOneWidget);
    expect(
      tester
          .widget<FilledButton>(find.widgetWithText(FilledButton, 'Continue'))
          .onPressed,
      isNull,
    );
  });

  testWidgets('renders the session setup', (tester) async {
    await tester.pumpWidget(QuizMachineApp(repository: FakeQuizRepository()));
    await tester.pumpAndSettle();

    expect(find.text('AI-103'), findsOneWidget);
    expect(find.text('Practice session'), findsOneWidget);
    expect(find.text('1/1 corpora indexed'), findsOneWidget);
    expect(find.text('1/1 chunks • Ready locally'), findsOneWidget);
    expect(find.text('Start session'), findsOneWidget);

    await expectLater(tester, meetsGuideline(labeledTapTargetGuideline));
  });

  testWidgets('opens useful learning dashboard and confirms scoped reset', (
    tester,
  ) async {
    final repository = _DashboardRepository();
    await tester.pumpWidget(QuizMachineApp(repository: repository));
    await tester.pumpAndSettle();

    await tester.tap(find.byTooltip('Learning dashboard'));
    await tester.pumpAndSettle();

    expect(find.text('Your preparation, made useful'), findsOneWidget);
    expect(find.text('12'), findsOneWidget);
    expect(find.text('Priority objectives'), findsOneWidget);
    expect(find.text('Recurring confusions'), findsOneWidget);
    final leadContext = tester.element(
      find.text('Your preparation, made useful'),
    );
    expect(Theme.of(leadContext).textTheme.headlineMedium?.fontFamily, 'Doto');

    await tester.tap(find.text('Reset data'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('AI-103 statistics'));
    await tester.pump();
    await tester.enterText(find.byType(TextField), 'AI-103');
    await tester.pump();
    final resetButton = tester.widget<FilledButton>(
      find.widgetWithText(FilledButton, 'Reset selected data'),
    );
    expect(resetButton.onPressed, isNotNull);
    resetButton.onPressed!();
    await tester.pumpAndSettle();

    expect(repository.resetScope, ProgressResetScope.certification);
    expect(find.text('Learning data reset completed.'), findsOneWidget);
  });

  testWidgets('switches the certification and reloads its course domains', (
    tester,
  ) async {
    final repository = FakeQuizRepository();
    await tester.pumpWidget(QuizMachineApp(repository: repository));
    await tester.pumpAndSettle();

    await tester.tap(find.byType(DropdownButton<String>).first);
    await tester.pumpAndSettle();
    await tester.tap(
      find.text('AI-901 — Microsoft Azure AI Fundamentals').last,
    );
    await tester.pumpAndSettle();

    expect(repository.lastCatalogCertificationCode, 'AI-901');
    expect(find.text('AI-901'), findsOneWidget);
    expect(find.text('Identify AI concepts and capabilities'), findsNothing);
  });

  testWidgets('completes the answer workflow', (tester) async {
    await tester.pumpWidget(QuizMachineApp(repository: FakeQuizRepository()));
    await tester.pumpAndSettle();

    final startButton = find.widgetWithText(FilledButton, 'Start session');
    await tester.ensureVisible(startButton);
    await tester.tap(startButton);
    await tester.pumpAndSettle();

    expect(
      find.text('Which option provides the strongest evaluation baseline?'),
      findsOneWidget,
    );

    await tester.tap(find.text('A representative test dataset'));
    await tester.pump();
    final checkButton = find.widgetWithText(FilledButton, 'Check answer');
    await tester.ensureVisible(checkButton);
    await tester.tap(checkButton);
    await tester.pumpAndSettle();

    expect(find.text('Correct'), findsOneWidget);
    expect(
      find.text('A representative dataset makes evaluations repeatable.'),
      findsOneWidget,
    );
  });

  testWidgets(
    'maps stable option ids to presentation letters after shuffling',
    (tester) async {
      await tester.pumpWidget(
        QuizMachineApp(repository: _ShuffledAnswerRepository()),
      );
      await tester.pumpAndSettle();

      final startButton = find.widgetWithText(FilledButton, 'Start session');
      await tester.ensureVisible(startButton);
      await tester.tap(startButton);
      await tester.pumpAndSettle();

      expect(find.text('A'), findsOneWidget);
      expect(find.text('opt_1'), findsNothing);

      await tester.tap(find.text('A representative test dataset'));
      await tester.pump();
      await tester.tap(find.widgetWithText(FilledButton, 'Check answer'));
      await tester.pumpAndSettle();

      expect(
        find.text('Correct answer: D — A longer system prompt'),
        findsOneWidget,
      );
      expect(find.text('What mattered'), findsOneWidget);
      expect(find.text('Rule to remember'), findsOneWidget);
      expect(find.text('Why your choice misses'), findsOneWidget);
      expect(find.text('Takeaway'), findsOneWidget);
    },
  );

  testWidgets('renders generated case-study context', (tester) async {
    await tester.pumpWidget(QuizMachineApp(repository: FakeQuizRepository()));
    await tester.pumpAndSettle();

    final cases = find.text('Cases');
    await tester.ensureVisible(cases);
    await tester.tap(cases);
    await tester.pumpAndSettle();

    final startButton = find.widgetWithText(FilledButton, 'Start session');
    await tester.ensureVisible(startButton);
    await tester.tap(startButton);
    await tester.pumpAndSettle();

    expect(find.text('Contoso evaluation rollout'), findsOneWidget);
    expect(find.text('Requirements'), findsOneWidget);
    expect(
      find.text('Measure quality against stable examples.'),
      findsOneWidget,
    );
  });
}
