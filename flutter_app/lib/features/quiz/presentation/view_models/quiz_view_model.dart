import 'package:flutter/foundation.dart';

import '../../data/quiz_repository.dart';
import '../../domain/quiz_models.dart';

enum QuizStage { loading, ready, generating, active, complete }

class QuizViewModel extends ChangeNotifier {
  QuizViewModel(this._repository);

  final QuizRepository _repository;

  QuizStage _stage = QuizStage.loading;
  QuizCatalog _catalog = QuizCatalog.empty;
  QuizProgress _progress = QuizProgress.empty;
  QuizMode _mode = QuizMode.shuffle;
  QuizDifficulty _difficulty = QuizDifficulty.random;
  QuizQuestionFormat _questionFormat = QuizQuestionFormat.standard;
  int _questionCount = 1;
  String _selectedCertificationCode = 'AI-103';
  String? _selectedDomain;
  String? _selectedChapterId;
  List<QuizQuestion> _questions = const [];
  int _currentIndex = 0;
  String? _selectedOptionId;
  QuizAnswerResult? _answerResult;
  String? _error;
  int _generatedCount = 0;
  int _generationTotal = 10;
  int _generationAttempts = 0;
  int _generationRejected = 0;
  int _generationReused = 0;
  String _generationPhase = 'queued';
  int _corpusCompleted = 0;
  int _corpusTotal = 0;
  int _corpusAttempts = 0;
  int _corpusRetries = 0;
  String _generationMessage = 'Preparing local generation...';
  bool _cancellingGeneration = false;
  bool _checkingAnswer = false;
  bool _disposed = false;
  DateTime? _questionStartedAt;

  QuizStage get stage => _stage;
  QuizCatalog get catalog => _catalog;
  QuizProgress get progress => _progress;
  QuizMode get mode => _mode;
  QuizDifficulty get difficulty => _difficulty;
  QuizQuestionFormat get questionFormat => _questionFormat;
  int get questionCount => _questionCount;
  String get selectedCertificationCode => _selectedCertificationCode;
  String? get selectedDomain => _selectedDomain;
  String? get selectedChapterId => _selectedChapterId;
  String? get selectedOptionId => _selectedOptionId;
  QuizAnswerResult? get answerResult => _answerResult;
  String? get error => _error;
  int get generatedCount => _generatedCount;
  int get generationTotal => _generationTotal;
  int get generationAttempts => _generationAttempts;
  int get generationRejected => _generationRejected;
  int get generationReused => _generationReused;
  String get generationPhase => _generationPhase;
  int get corpusCompleted => _corpusCompleted;
  int get corpusTotal => _corpusTotal;
  int get corpusAttempts => _corpusAttempts;
  int get corpusRetries => _corpusRetries;
  String get generationMessage => _generationMessage;
  bool get cancellingGeneration => _cancellingGeneration;
  int get currentIndex => _currentIndex;
  int get totalQuestions => _questions.length;
  bool get checkingAnswer => _checkingAnswer;
  bool get isBusy =>
      _stage == QuizStage.loading || _stage == QuizStage.generating;

  QuizQuestion? get currentQuestion {
    if (_questions.isEmpty || _currentIndex >= _questions.length) return null;
    return _questions[_currentIndex];
  }

  double get sessionProgress {
    if (_questions.isEmpty) return 0;
    return (_currentIndex + 1) / _questions.length;
  }

  Future<void> initialize() async {
    _stage = QuizStage.loading;
    _notify();
    try {
      final catalog = await _repository.loadCatalog();
      final progress = await _repository.loadProgress(
        certificationCode: catalog.selectedCertificationCode,
      );
      if (_disposed) return;
      _catalog = catalog;
      _selectedCertificationCode = _catalog.selectedCertificationCode;
      _progress = progress;
      _selectedDomain = _catalog.domains.firstOrNull;
      _selectedChapterId = _catalog.chapters.firstOrNull?.id;
      _stage = QuizStage.ready;
    } catch (exception) {
      if (_disposed) return;
      _error = exception.toString();
      _stage = QuizStage.ready;
    }
    _notify();
  }

  void setMode(QuizMode value) {
    _mode = value;
    _selectedDomain ??= _catalog.domains.firstOrNull;
    _selectedChapterId ??= _catalog.chapters.firstOrNull?.id;
    _notify();
  }

  void setDifficulty(QuizDifficulty value) {
    _difficulty = value;
    _notify();
  }

  void setQuestionFormat(QuizQuestionFormat value) {
    _questionFormat = value;
    _notify();
  }

  void setQuestionCount(int value) {
    _questionCount = value.clamp(1, 50);
    _notify();
  }

  void setDomain(String? value) {
    _selectedDomain = value;
    _notify();
  }

  void setChapter(String? value) {
    _selectedChapterId = value;
    _notify();
  }

  Future<void> setCertification(String? value) async {
    if (value == null || value == _selectedCertificationCode || isBusy) return;
    _stage = QuizStage.loading;
    _error = null;
    _notify();
    try {
      final catalog = await _repository.loadCatalog(certificationCode: value);
      if (_disposed) return;
      _catalog = catalog;
      _selectedCertificationCode = catalog.selectedCertificationCode;
      _progress = await _repository.loadProgress(
        certificationCode: catalog.selectedCertificationCode,
      );
      if (_disposed) return;
      _selectedDomain = catalog.domains.firstOrNull;
      _selectedChapterId = catalog.chapters.firstOrNull?.id;
      if (_mode == QuizMode.chapter && catalog.chapters.isEmpty) {
        _mode = QuizMode.shuffle;
      }
    } catch (exception) {
      if (_disposed) return;
      _error = exception.toString();
    }
    _stage = QuizStage.ready;
    _notify();
  }

  Future<void> generateQuiz() async {
    if (_mode == QuizMode.domain && _selectedDomain == null) {
      _showError('No domain is available for this corpus.');
      return;
    }
    if (_mode == QuizMode.chapter && _selectedChapterId == null) {
      _showError('No chapter is available for this corpus.');
      return;
    }

    _stage = QuizStage.generating;
    _generatedCount = 0;
    _generationTotal = _questionCount;
    _generationAttempts = 0;
    _generationRejected = 0;
    _generationReused = 0;
    _generationPhase = 'queued';
    _corpusCompleted = 0;
    _corpusTotal = 0;
    _corpusAttempts = 0;
    _corpusRetries = 0;
    _generationMessage = 'Preparing local generation...';
    _cancellingGeneration = false;
    _questions = const [];
    _currentIndex = 0;
    _selectedOptionId = null;
    _answerResult = null;
    _error = null;
    _notify();

    try {
      final questions = await _repository.generateBatch(
        certificationCode: _selectedCertificationCode,
        count: _questionCount,
        mode: _mode,
        difficulty: _difficulty,
        questionFormat: _questionFormat,
        domain: _selectedDomain,
        chapterId: _selectedChapterId,
        onProgress: (progress) {
          if (_disposed) return;
          _generatedCount = progress.completed;
          _generationTotal = progress.total;
          _generationAttempts = progress.attempts;
          _generationRejected = progress.rejected;
          _generationReused = progress.reused;
          _generationPhase = progress.phase;
          _corpusCompleted = progress.corpusCompleted;
          _corpusTotal = progress.corpusTotal;
          _corpusAttempts = progress.corpusAttempts;
          _corpusRetries = progress.corpusRetries;
          _generationMessage = progress.message;
          _notify();
        },
      );
      if (_disposed) return;
      _questions = List<QuizQuestion>.of(questions);
      _questionStartedAt = DateTime.now();
      _stage = QuizStage.active;
    } on QuizGenerationCancelled {
      if (_disposed) return;
      _stage = QuizStage.ready;
    } catch (exception) {
      if (_disposed) return;
      _error = exception.toString();
      _stage = QuizStage.ready;
    }
    _cancellingGeneration = false;
    _notify();
  }

  Future<void> cancelGeneration() async {
    if (_stage != QuizStage.generating || _cancellingGeneration) return;
    _cancellingGeneration = true;
    _generationMessage = 'Cancelling after the current local model call...';
    _notify();
    try {
      await _repository.cancelGeneration();
    } catch (exception) {
      if (_disposed) return;
      _cancellingGeneration = false;
      _error = exception.toString();
      _notify();
    }
  }

  void selectOption(String optionId) {
    if (_answerResult != null || _checkingAnswer) return;
    _selectedOptionId = optionId;
    _notify();
  }

  Future<void> submitAnswer() async {
    final question = currentQuestion;
    final option = _selectedOptionId;
    if (question == null || option == null || _checkingAnswer) return;

    _checkingAnswer = true;
    _error = null;
    _notify();
    try {
      final result = await _repository.submitAnswer(
        question.questionId,
        option,
        elapsedSeconds: _questionStartedAt == null
            ? null
            : DateTime.now().difference(_questionStartedAt!).inMilliseconds /
                1000,
      );
      if (_disposed) return;
      _answerResult = result;
      _progress = result.progress;
    } catch (exception) {
      if (_disposed) return;
      _error = exception.toString();
    }
    _checkingAnswer = false;
    _notify();
  }

  void nextQuestion() {
    final answeredQuestion = currentQuestion;
    if (_answerResult?.correct == false && answeredQuestion != null) {
      final objective = answeredQuestion.learningObjective;
      if (objective.isNotEmpty) {
        var remediationIndex = -1;
        for (var index = _currentIndex + 2;
            index < _questions.length;
            index += 1) {
          if (_questions[index].learningObjective == objective) {
            remediationIndex = index;
            break;
          }
        }
        if (remediationIndex > _currentIndex + 1) {
          final next = _questions[_currentIndex + 1];
          _questions[_currentIndex + 1] = _questions[remediationIndex];
          _questions[remediationIndex] = next;
        }
      }
    }
    if (_currentIndex + 1 >= _questions.length) {
      _questions = const [];
      _currentIndex = 0;
      _selectedOptionId = null;
      _answerResult = null;
      _stage = QuizStage.complete;
      _questionStartedAt = null;
    } else {
      _currentIndex += 1;
      _selectedOptionId = null;
      _answerResult = null;
      _error = null;
      _questionStartedAt = DateTime.now();
    }
    _notify();
  }

  void prepareNewQuiz() {
    _stage = QuizStage.ready;
    _notify();
  }

  void dismissError() {
    _error = null;
    _notify();
  }

  Future<void> resetProgress(ProgressResetScope scope) async {
    try {
      _progress = await _repository.resetProgress(
        scope: scope,
        certificationCode:
            scope == ProgressResetScope.all ? null : _selectedCertificationCode,
      );
      if (_disposed) return;
      _error = null;
    } catch (exception) {
      if (_disposed) return;
      _error = exception.toString();
      rethrow;
    } finally {
      _notify();
    }
  }

  void _showError(String message) {
    _error = message;
    _notify();
  }

  void _notify() {
    if (!_disposed) notifyListeners();
  }

  @override
  void dispose() {
    _disposed = true;
    _repository.dispose();
    super.dispose();
  }
}
