import 'package:flutter/foundation.dart';

enum QuizMode { shuffle, domain, chapter }

extension QuizModeLabel on QuizMode {
  String get apiValue => name;

  String get label => switch (this) {
        QuizMode.shuffle => 'Mixed',
        QuizMode.domain => 'Domain',
        QuizMode.chapter => 'Chapter',
      };
}

enum QuizDifficulty { random, easy, medium, hard }

extension QuizDifficultyLabel on QuizDifficulty {
  String get apiValue => name;

  String get label => switch (this) {
        QuizDifficulty.random => 'Adaptive mix',
        QuizDifficulty.easy => 'Easy',
        QuizDifficulty.medium => 'Medium',
        QuizDifficulty.hard => 'Hard',
      };
}

enum QuizQuestionFormat { mixed, standard, caseStudy }

extension QuizQuestionFormatLabel on QuizQuestionFormat {
  String get apiValue => switch (this) {
        QuizQuestionFormat.mixed => 'mixed',
        QuizQuestionFormat.standard => 'standard',
        QuizQuestionFormat.caseStudy => 'case_study',
      };

  String get label => switch (this) {
        QuizQuestionFormat.mixed => 'Mixed',
        QuizQuestionFormat.standard => 'QCM',
        QuizQuestionFormat.caseStudy => 'Case studies',
      };
}

enum QuizQuestionType { standard, caseStudy }

@immutable
class QuizGenerationProgress {
  const QuizGenerationProgress({
    required this.completed,
    required this.total,
    required this.attempts,
    required this.rejected,
    required this.message,
    this.reused = 0,
    this.phase = 'generating_questions',
    this.corpusCompleted = 0,
    this.corpusTotal = 0,
    this.corpusAttempts = 0,
    this.corpusRetries = 0,
  });

  final int completed;
  final int total;
  final int attempts;
  final int rejected;
  final int reused;
  final String message;
  final String phase;
  final int corpusCompleted;
  final int corpusTotal;
  final int corpusAttempts;
  final int corpusRetries;

  bool get isPreparingCorpus => phase == 'preparing_corpus';

  factory QuizGenerationProgress.fromJson(
    Map<String, dynamic> json, {
    required int fallbackTotal,
  }) {
    return QuizGenerationProgress(
      completed: (json['completed'] as num?)?.toInt() ?? 0,
      total: (json['total'] as num?)?.toInt() ?? fallbackTotal,
      attempts: (json['attempts'] as num?)?.toInt() ?? 0,
      rejected: (json['rejected'] as num?)?.toInt() ?? 0,
      reused: (json['reused'] as num?)?.toInt() ?? 0,
      message: json['message']?.toString() ?? 'Generating locally...',
      phase: json['phase']?.toString() ?? 'generating_questions',
      corpusCompleted: (json['corpus_completed'] as num?)?.toInt() ?? 0,
      corpusTotal: (json['corpus_total'] as num?)?.toInt() ?? 0,
      corpusAttempts: (json['corpus_attempts'] as num?)?.toInt() ?? 0,
      corpusRetries: (json['corpus_retries'] as num?)?.toInt() ?? 0,
    );
  }
}

@immutable
class CertificationItem {
  const CertificationItem({
    required this.code,
    required this.title,
    required this.studyGuideUrl,
  });

  final String code;
  final String title;
  final String studyGuideUrl;

  String get label => '$code — $title';

  factory CertificationItem.fromJson(Map<String, dynamic> json) {
    return CertificationItem(
      code: json['code']?.toString() ?? '',
      title: json['title']?.toString() ?? '',
      studyGuideUrl: json['study_guide_url']?.toString() ?? '',
    );
  }
}

@immutable
class QuizCaseStudy {
  const QuizCaseStudy({
    required this.title,
    required this.scenario,
    required this.requirements,
  });

  final String title;
  final String scenario;
  final List<String> requirements;

  factory QuizCaseStudy.fromJson(Map<String, dynamic> json) {
    return QuizCaseStudy(
      title: json['title'] as String,
      scenario: json['scenario'] as String,
      requirements: (json['requirements'] as List<dynamic>).cast<String>(),
    );
  }
}

@immutable
class QuizOption {
  const QuizOption({required this.id, required this.text});

  final String id;
  final String text;

  factory QuizOption.fromJson(Map<String, dynamic> json) {
    return QuizOption(
      id: json['id'] as String,
      text: json['text'] as String,
    );
  }
}

@immutable
class QuizQuestion {
  const QuizQuestion({
    required this.questionId,
    this.certificationCode = 'AI-103',
    required this.questionType,
    required this.caseStudy,
    required this.question,
    required this.options,
    required this.topic,
    required this.domain,
    required this.difficulty,
    required this.supportingSourceIds,
    this.learningObjective = '',
  });

  final String questionId;
  final String certificationCode;
  final QuizQuestionType questionType;
  final QuizCaseStudy? caseStudy;
  final String question;
  final List<QuizOption> options;
  final String topic;
  final String domain;
  final String difficulty;
  final List<String> supportingSourceIds;
  final String learningObjective;

  factory QuizQuestion.fromJson(Map<String, dynamic> json) {
    final rawType = json['question_type']?.toString() ?? 'standard';
    final rawCaseStudy = json['case_study'];
    return QuizQuestion(
      questionId: json['question_id'] as String,
      certificationCode: json['certification_code']?.toString() ?? 'AI-103',
      questionType: rawType == 'case_study'
          ? QuizQuestionType.caseStudy
          : QuizQuestionType.standard,
      caseStudy: rawCaseStudy is Map<String, dynamic>
          ? QuizCaseStudy.fromJson(rawCaseStudy)
          : null,
      question: json['question'] as String,
      options: (json['options'] as List<dynamic>)
          .map((item) => QuizOption.fromJson(item as Map<String, dynamic>))
          .toList(growable: false),
      topic: json['topic'] as String,
      domain: json['domain'] as String,
      difficulty: json['difficulty'] as String,
      supportingSourceIds:
          (json['supporting_source_ids'] as List<dynamic>).cast<String>(),
      learningObjective: json['learning_objective']?.toString() ?? '',
    );
  }
}

@immutable
class ChapterItem {
  const ChapterItem({
    required this.id,
    required this.topic,
    required this.domain,
    required this.start,
    this.sourceId = '',
    this.sourceTitle = '',
  });

  final String id;
  final String topic;
  final String domain;
  final String start;
  final String sourceId;
  final String sourceTitle;

  String get label {
    final chapterLabel = start.isEmpty ? topic : '$start  $topic';
    return sourceTitle.isEmpty ? chapterLabel : '$sourceTitle — $chapterLabel';
  }

  factory ChapterItem.fromJson(Map<String, dynamic> json) {
    return ChapterItem(
      id: json['id'] as String,
      topic: json['topic']?.toString() ?? 'Unknown topic',
      domain: json['domain']?.toString() ?? 'Unknown domain',
      start: json['start']?.toString() ?? '',
      sourceId: json['source_id']?.toString() ?? '',
      sourceTitle: json['source_title']?.toString() ?? '',
    );
  }
}

@immutable
class CorpusSource {
  const CorpusSource({
    required this.id,
    required this.title,
    required this.status,
    required this.expectedChunks,
    required this.indexedChunks,
    required this.chapterCount,
    this.reason = '',
  });

  final String id;
  final String title;
  final String status;
  final int expectedChunks;
  final int indexedChunks;
  final int chapterCount;
  final String reason;

  bool get isCurrent => status == 'indexed';
  bool get isExcluded => status == 'excluded';

  factory CorpusSource.fromJson(Map<String, dynamic> json) {
    return CorpusSource(
      id: json['id']?.toString() ?? '',
      title: json['title']?.toString() ?? 'Unknown corpus',
      status: json['status']?.toString() ?? 'missing',
      expectedChunks: (json['expected_chunks'] as num?)?.toInt() ?? 0,
      indexedChunks: (json['indexed_chunks'] as num?)?.toInt() ?? 0,
      chapterCount: (json['chapter_count'] as num?)?.toInt() ?? 0,
      reason: json['reason']?.toString() ?? '',
    );
  }
}

@immutable
class CorpusCoverage {
  const CorpusCoverage({
    required this.complete,
    required this.expectedSources,
    required this.indexedSources,
    required this.expectedChunks,
    required this.indexedChunks,
  });

  static const empty = CorpusCoverage(
    complete: false,
    expectedSources: 0,
    indexedSources: 0,
    expectedChunks: 0,
    indexedChunks: 0,
  );

  final bool complete;
  final int expectedSources;
  final int indexedSources;
  final int expectedChunks;
  final int indexedChunks;

  factory CorpusCoverage.fromJson(Map<String, dynamic> json) {
    return CorpusCoverage(
      complete: json['complete'] == true,
      expectedSources: (json['expected_sources'] as num?)?.toInt() ?? 0,
      indexedSources: (json['indexed_sources'] as num?)?.toInt() ?? 0,
      expectedChunks: (json['expected_chunks'] as num?)?.toInt() ?? 0,
      indexedChunks: (json['indexed_chunks'] as num?)?.toInt() ?? 0,
    );
  }
}

@immutable
class QuizCatalog {
  const QuizCatalog({
    required this.domains,
    required this.chapters,
    this.certifications = const [],
    this.selectedCertificationCode = 'AI-103',
    this.knowledgeProvider = 'local',
    this.sources = const [],
    this.coverage = CorpusCoverage.empty,
  });

  static const empty = QuizCatalog(domains: [], chapters: []);

  final List<String> domains;
  final List<ChapterItem> chapters;
  final List<CertificationItem> certifications;
  final String selectedCertificationCode;
  final String knowledgeProvider;
  final List<CorpusSource> sources;
  final CorpusCoverage coverage;

  factory QuizCatalog.fromJson(Map<String, dynamic> json) {
    return QuizCatalog(
      certifications: (json['certifications'] as List<dynamic>? ?? const [])
          .map(
            (item) => CertificationItem.fromJson(
              item as Map<String, dynamic>,
            ),
          )
          .toList(growable: false),
      selectedCertificationCode:
          (json['selected_certification'] as Map<String, dynamic>?)?['code']
                  ?.toString() ??
              'AI-103',
      knowledgeProvider: json['knowledge_provider']?.toString() ?? 'local',
      domains: (json['domains'] as List<dynamic>? ?? const []).cast<String>(),
      chapters: (json['chapters'] as List<dynamic>? ?? const [])
          .map((item) => ChapterItem.fromJson(item as Map<String, dynamic>))
          .toList(growable: false),
      sources: (json['sources'] as List<dynamic>? ?? const [])
          .map((item) => CorpusSource.fromJson(item as Map<String, dynamic>))
          .toList(growable: false),
      coverage: json['coverage'] is Map<String, dynamic>
          ? CorpusCoverage.fromJson(
              json['coverage'] as Map<String, dynamic>,
            )
          : CorpusCoverage.empty,
    );
  }
}

@immutable
class QuizProgress {
  const QuizProgress({
    required this.asked,
    required this.correct,
    required this.accuracy,
    this.recentAccuracy = 0,
    this.averageSeconds,
    this.domains = const [],
    this.objectives = const [],
    this.confusions = const [],
    this.recentAttemptCount = 0,
  });

  static const empty = QuizProgress(asked: 0, correct: 0, accuracy: 0);

  final int asked;
  final int correct;
  final double accuracy;
  final double recentAccuracy;
  final double? averageSeconds;
  final List<ProgressMetric> domains;
  final List<ProgressMetric> objectives;
  final List<ProgressConfusion> confusions;
  final int recentAttemptCount;

  int get percent => (accuracy * 100).round();
  int get recentPercent => (recentAccuracy * 100).round();
  int get incorrect => asked - correct;

  factory QuizProgress.fromJson(Map<String, dynamic> json) {
    final asked = (json['asked'] as num?)?.toInt() ?? 0;
    final correct = (json['correct'] as num?)?.toInt() ?? 0;
    final reportedAccuracy = (json['accuracy'] as num?)?.toDouble();
    return QuizProgress(
      asked: asked,
      correct: correct,
      accuracy: reportedAccuracy ?? (asked == 0 ? 0 : correct / asked),
      recentAccuracy: (json['recent_accuracy'] as num?)?.toDouble() ?? 0,
      averageSeconds: (json['average_seconds'] as num?)?.toDouble(),
      domains: _progressMetrics(json['by_domain'], objective: false),
      objectives: _progressMetrics(json['by_objective'], objective: true),
      confusions: (json['confusions'] as List<dynamic>? ?? const [])
          .whereType<Map<String, dynamic>>()
          .map(ProgressConfusion.fromJson)
          .toList(growable: false),
      recentAttemptCount:
          (json['recent_attempts'] as List<dynamic>? ?? const []).length,
    );
  }

  static List<ProgressMetric> _progressMetrics(
    Object? raw, {
    required bool objective,
  }) {
    if (raw is! Map<String, dynamic>) return const [];
    final metrics = raw.entries
        .where((entry) => entry.value is Map<String, dynamic>)
        .map(
          (entry) => ProgressMetric.fromJson(
            entry.value as Map<String, dynamic>,
            fallbackLabel: entry.key,
            objective: objective,
          ),
        )
        .toList();
    metrics.sort((left, right) {
      final accuracy = left.accuracy.compareTo(right.accuracy);
      return accuracy != 0 ? accuracy : right.asked.compareTo(left.asked);
    });
    return List.unmodifiable(metrics);
  }
}

@immutable
class ProgressMetric {
  const ProgressMetric({
    required this.label,
    required this.asked,
    required this.correct,
    required this.accuracy,
    required this.mastery,
    this.domain,
    this.averageSeconds,
  });

  final String label;
  final int asked;
  final int correct;
  final double accuracy;
  final double mastery;
  final String? domain;
  final double? averageSeconds;

  int get percent => (accuracy * 100).round();
  int get masteryPercent => (mastery * 100).round();

  factory ProgressMetric.fromJson(
    Map<String, dynamic> json, {
    required String fallbackLabel,
    required bool objective,
  }) {
    final asked = (json['asked'] as num?)?.toInt() ?? 0;
    final correct = (json['correct'] as num?)?.toInt() ?? 0;
    return ProgressMetric(
      label: objective
          ? json['learning_objective']?.toString() ?? fallbackLabel
          : fallbackLabel,
      asked: asked,
      correct: correct,
      accuracy: (json['accuracy'] as num?)?.toDouble() ??
          (asked == 0 ? 0 : correct / asked),
      mastery: (json['mastery'] as num?)?.toDouble() ??
          (asked == 0 ? 0 : (correct + 1) / (asked + 2)),
      domain: json['domain']?.toString(),
      averageSeconds: (json['average_seconds'] as num?)?.toDouble(),
    );
  }
}

@immutable
class ProgressConfusion {
  const ProgressConfusion({
    required this.learningObjective,
    required this.selectedOptionText,
    required this.correctOptionText,
    required this.count,
  });

  final String learningObjective;
  final String selectedOptionText;
  final String correctOptionText;
  final int count;

  factory ProgressConfusion.fromJson(Map<String, dynamic> json) {
    return ProgressConfusion(
      learningObjective:
          json['learning_objective']?.toString() ?? 'Unknown objective',
      selectedOptionText: json['selected_option_text']?.toString() ?? '',
      correctOptionText: json['correct_option_text']?.toString() ?? '',
      count: (json['count'] as num?)?.toInt() ?? 1,
    );
  }
}

enum ProgressResetScope {
  recentActivity('recent_activity'),
  adaptiveProfile('adaptive_profile'),
  certification('certification'),
  all('all');

  const ProgressResetScope(this.apiValue);

  final String apiValue;
}

@immutable
class OptionExplanation {
  const OptionExplanation({
    required this.optionId,
    required this.explanation,
  });

  final String optionId;
  final String explanation;

  factory OptionExplanation.fromJson(Map<String, dynamic> json) {
    return OptionExplanation(
      optionId: json['option_id'] as String,
      explanation: json['explanation'] as String,
    );
  }
}

@immutable
class QuizAnswerResult {
  const QuizAnswerResult({
    required this.correct,
    required this.selectedOptionId,
    required this.correctOptionId,
    required this.explanation,
    required this.optionExplanations,
    required this.progress,
    this.sourceUrls = const [],
    this.decisiveClue = '',
    this.learningRule = '',
    this.selectedOptionFeedback = '',
    this.correctOptionFeedback = '',
    this.takeaway = '',
    this.nextFocus,
  });

  final bool correct;
  final String selectedOptionId;
  final String correctOptionId;
  final String explanation;
  final List<OptionExplanation> optionExplanations;
  final QuizProgress progress;
  final List<String> sourceUrls;
  final String decisiveClue;
  final String learningRule;
  final String selectedOptionFeedback;
  final String correctOptionFeedback;
  final String takeaway;
  final String? nextFocus;

  factory QuizAnswerResult.fromJson(Map<String, dynamic> json) {
    return QuizAnswerResult(
      correct: json['correct'] == true,
      selectedOptionId: json['selected_option_id'] as String,
      correctOptionId: json['correct_option_id'] as String,
      explanation: json['explanation'] as String,
      optionExplanations: (json['option_explanations'] as List<dynamic>)
          .map(
            (item) => OptionExplanation.fromJson(item as Map<String, dynamic>),
          )
          .toList(growable: false),
      progress: QuizProgress.fromJson(
        json['progress'] as Map<String, dynamic>,
      ),
      sourceUrls: (json['source_urls'] as List<dynamic>? ?? const [])
          .map((item) => item.toString())
          .toList(growable: false),
      decisiveClue: json['decisive_clue']?.toString() ?? '',
      learningRule: json['learning_rule']?.toString() ?? '',
      selectedOptionFeedback:
          json['selected_option_feedback']?.toString() ?? '',
      correctOptionFeedback: json['correct_option_feedback']?.toString() ?? '',
      takeaway: json['takeaway']?.toString() ?? '',
      nextFocus: json['next_focus']?.toString(),
    );
  }
}
