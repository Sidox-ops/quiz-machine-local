import '../domain/quiz_models.dart';
import 'quiz_api_service.dart';

typedef GenerationProgress = void Function(QuizGenerationProgress progress);

class QuizGenerationCancelled implements Exception {
  const QuizGenerationCancelled();
}

abstract interface class QuizRepository {
  Future<QuizCatalog> loadCatalog({String? certificationCode});

  Future<QuizProgress> loadProgress({String? certificationCode});

  Future<QuizProgress> resetProgress({
    required ProgressResetScope scope,
    String? certificationCode,
  });

  Future<List<QuizQuestion>> generateBatch({
    required String certificationCode,
    required int count,
    required QuizMode mode,
    required QuizDifficulty difficulty,
    required QuizQuestionFormat questionFormat,
    required String? domain,
    required String? chapterId,
    required GenerationProgress onProgress,
  });

  Future<QuizAnswerResult> submitAnswer(String questionId, String option,
      {double? elapsedSeconds});

  Future<void> cancelGeneration();

  void dispose();
}

class RemoteQuizRepository implements QuizRepository {
  RemoteQuizRepository(this._service);

  final QuizApiService _service;
  String? _activeJobId;

  @override
  Future<QuizCatalog> loadCatalog({String? certificationCode}) async {
    return QuizCatalog.fromJson(
      await _service.catalog(certificationCode: certificationCode),
    );
  }

  @override
  Future<QuizProgress> loadProgress({String? certificationCode}) async {
    return QuizProgress.fromJson(
      await _service.progress(certificationCode: certificationCode),
    );
  }

  @override
  Future<QuizProgress> resetProgress({
    required ProgressResetScope scope,
    String? certificationCode,
  }) async {
    return QuizProgress.fromJson(
      await _service.resetProgress(
        scope: scope.apiValue,
        certificationCode: certificationCode,
      ),
    );
  }

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
    final start = await _service.startBatch(
      certificationCode: certificationCode,
      count: count,
      mode: mode.apiValue,
      difficulty: difficulty.apiValue,
      questionType: questionFormat.apiValue,
      domain: mode == QuizMode.domain ? domain : null,
      chapterId: mode == QuizMode.chapter ? chapterId : null,
    );
    final jobId = start['job_id'] as String;
    _activeJobId = jobId;

    try {
      while (true) {
        final payload = await _service.batchStatus(jobId);
        onProgress(QuizGenerationProgress.fromJson(
          payload,
          fallbackTotal: count,
        ));

        switch (payload['status']?.toString()) {
          case 'cancelled':
            throw const QuizGenerationCancelled();
          case 'failed':
            throw QuizApiException(
              payload['error']?.toString() ?? 'Question generation failed.',
            );
          case 'completed':
            final questions =
                (payload['questions'] as List<dynamic>? ?? const [])
                    .map(
                      (item) =>
                          QuizQuestion.fromJson(item as Map<String, dynamic>),
                    )
                    .toList(growable: false);
            if (questions.length != count) {
              throw QuizApiException(
                'The batch completed with ${questions.length}/$count questions.',
              );
            }
            return questions;
        }

        await Future<void>.delayed(const Duration(milliseconds: 650));
      }
    } finally {
      if (_activeJobId == jobId) _activeJobId = null;
    }
  }

  @override
  Future<void> cancelGeneration() async {
    final jobId = _activeJobId;
    if (jobId == null) return;
    await _service.cancelBatch(jobId);
  }

  @override
  Future<QuizAnswerResult> submitAnswer(String questionId, String option,
      {double? elapsedSeconds}) async {
    return QuizAnswerResult.fromJson(
      await _service.answer(
        questionId,
        option,
        elapsedSeconds: elapsedSeconds,
      ),
    );
  }

  @override
  void dispose() => _service.close();
}
