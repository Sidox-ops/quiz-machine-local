import 'package:ai103_quiz_ui/features/quiz/data/quiz_repository.dart';
import 'package:ai103_quiz_ui/features/quiz/domain/quiz_models.dart';
import 'package:ai103_quiz_ui/features/quiz/presentation/view_models/quiz_view_model.dart';
import 'package:flutter_test/flutter_test.dart';

import 'fakes/fake_quiz_repository.dart';

class _AdaptiveRepository extends FakeQuizRepository {
  @override
  Future<List<QuizQuestion>> generateBatch({
    required String certificationCode,
    required int count,
    required QuizMode mode,
    required QuizDifficulty difficulty,
    required QuizQuestionFormat questionFormat,
    required String? domain,
    required String? chapterId,
    required GenerationProgress onProgress,
  }) async {
    return [
      _question('q1', 'Objective A'),
      _question('q2', 'Objective B'),
      _question('q3', 'Objective A'),
    ];
  }

  QuizQuestion _question(String id, String objective) => QuizQuestion(
        questionId: id,
        questionType: QuizQuestionType.standard,
        caseStudy: null,
        question: 'Question $id',
        options: const [
          QuizOption(id: 'opt_1', text: 'One'),
          QuizOption(id: 'opt_2', text: 'Two'),
          QuizOption(id: 'opt_3', text: 'Three'),
          QuizOption(id: 'opt_4', text: 'Four'),
        ],
        topic: objective,
        domain: 'Domain',
        difficulty: 'hard',
        supportingSourceIds: const ['chunk'],
        learningObjective: objective,
      );

  @override
  Future<QuizAnswerResult> submitAnswer(String questionId, String option,
      {double? elapsedSeconds}) async {
    return const QuizAnswerResult(
      correct: false,
      selectedOptionId: 'opt_2',
      correctOptionId: 'opt_1',
      explanation: 'Correction',
      optionExplanations: [],
      progress: QuizProgress(asked: 1, correct: 0, accuracy: 0),
    );
  }
}

void main() {
  test('an error brings an already-generated remediation question next',
      () async {
    final viewModel = QuizViewModel(_AdaptiveRepository());
    await viewModel.initialize();
    viewModel.setQuestionCount(3);
    await viewModel.generateQuiz();

    expect(viewModel.currentQuestion?.questionId, 'q1');
    viewModel.selectOption('opt_2');
    await viewModel.submitAnswer();
    viewModel.nextQuestion();

    expect(viewModel.currentQuestion?.questionId, 'q3');
    viewModel.dispose();
  });
}
