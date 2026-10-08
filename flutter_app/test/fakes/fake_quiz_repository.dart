import 'package:quiz_machine_local/features/quiz/data/quiz_repository.dart';
import 'package:quiz_machine_local/features/quiz/domain/quiz_models.dart';

class FakeQuizRepository implements QuizRepository {
  bool disposed = false;
  String? lastCatalogCertificationCode;

  @override
  Future<QuizCatalog> loadCatalog({String? certificationCode}) async {
    lastCatalogCertificationCode = certificationCode;
    final selected = certificationCode ?? 'AI-103';
    return QuizCatalog(
      certifications: const [
        CertificationItem(
          code: 'AI-901',
          title: 'Microsoft Azure AI Fundamentals',
          studyGuideUrl: 'https://learn.microsoft.com/ai-901',
        ),
        CertificationItem(
          code: 'AI-103',
          title: 'Developing AI Apps and Agents on Azure',
          studyGuideUrl: 'https://learn.microsoft.com/ai-103',
        ),
        CertificationItem(
          code: 'AI-200',
          title: 'Developing AI Cloud Solutions on Azure',
          studyGuideUrl: 'https://learn.microsoft.com/ai-200',
        ),
        CertificationItem(
          code: 'AI-300',
          title:
              'Operationalizing Machine Learning and Generative AI Solutions',
          studyGuideUrl: 'https://learn.microsoft.com/ai-300',
        ),
        CertificationItem(
          code: 'AI-500',
          title: 'Designing and Implementing Multi-Agent AI Solutions',
          studyGuideUrl: 'https://learn.microsoft.com/ai-500',
        ),
      ],
      selectedCertificationCode: selected,
      knowledgeProvider: 'microsoft_learn_mcp',
      domains: selected == 'AI-901'
          ? const ['Identify AI concepts and capabilities']
          : const ['Plan and manage an Azure AI solution'],
      coverage: const CorpusCoverage(
        complete: true,
        expectedSources: 1,
        indexedSources: 1,
        expectedChunks: 1,
        indexedChunks: 1,
      ),
      sources: const [
        CorpusSource(
          id: 'reference/demo.json',
          title: 'Demo corpus',
          status: 'indexed',
          expectedChunks: 1,
          indexedChunks: 1,
          chapterCount: 1,
        ),
        CorpusSource(
          id: 'local/patterns.json',
          title: 'Question patterns',
          status: 'excluded',
          expectedChunks: 0,
          indexedChunks: 0,
          chapterCount: 0,
          reason: 'Question patterns are not factual grounding.',
        ),
      ],
      chapters: const [
        ChapterItem(
          id: 'chapter-1',
          topic: 'Plan an Azure AI solution',
          domain: 'Plan and manage an Azure AI solution',
          start: '00:00',
          sourceId: 'reference/demo.json',
          sourceTitle: 'Demo corpus',
        ),
      ],
    );
  }

  @override
  Future<QuizProgress> loadProgress({String? certificationCode}) async =>
      QuizProgress.empty;

  @override
  Future<QuizProgress> resetProgress({
    required ProgressResetScope scope,
    String? certificationCode,
  }) async =>
      QuizProgress.empty;

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
    onProgress(QuizGenerationProgress(
      completed: count,
      total: count,
      attempts: count,
      rejected: 0,
      message: 'All questions are ready.',
    ));
    return List.generate(
      count,
      (index) {
        final isCaseStudy = questionFormat == QuizQuestionFormat.caseStudy;
        return QuizQuestion(
          questionId: 'question-$index',
          questionType: isCaseStudy
              ? QuizQuestionType.caseStudy
              : QuizQuestionType.standard,
          caseStudy: isCaseStudy
              ? const QuizCaseStudy(
                  title: 'Contoso evaluation rollout',
                  scenario:
                      'A team is preparing a generative AI application for '
                      'production and needs a repeatable way to compare response '
                      'quality before each release.',
                  requirements: [
                    'Measure quality against stable examples.',
                    'Make results comparable between releases.',
                  ],
                )
              : null,
          question: 'Which option provides the strongest evaluation baseline?',
          options: const [
            QuizOption(id: 'opt_1', text: 'A representative test dataset'),
            QuizOption(id: 'opt_2', text: 'A larger production quota'),
            QuizOption(id: 'opt_3', text: 'A different resource group'),
            QuizOption(id: 'opt_4', text: 'A longer system prompt'),
          ],
          topic: 'Evaluation',
          domain: 'Plan and manage an Azure AI solution',
          difficulty: 'medium',
          supportingSourceIds: const ['chunk-1'],
        );
      },
      growable: false,
    );
  }

  @override
  Future<void> cancelGeneration() async {}

  @override
  Future<QuizAnswerResult> submitAnswer(String questionId, String option,
      {double? elapsedSeconds}) async {
    return const QuizAnswerResult(
      correct: true,
      selectedOptionId: 'opt_1',
      correctOptionId: 'opt_1',
      explanation: 'A representative dataset makes evaluations repeatable.',
      optionExplanations: [
        OptionExplanation(
          optionId: 'opt_1',
          explanation: 'It provides a stable quality baseline.',
        ),
        OptionExplanation(
          optionId: 'opt_2',
          explanation: 'Quota does not measure answer quality.',
        ),
        OptionExplanation(
          optionId: 'opt_3',
          explanation: 'Resource placement does not create a baseline.',
        ),
        OptionExplanation(
          optionId: 'opt_4',
          explanation: 'Prompt length is not an evaluation strategy.',
        ),
      ],
      progress: QuizProgress(asked: 1, correct: 1, accuracy: 1),
    );
  }

  @override
  void dispose() {
    disposed = true;
  }
}
