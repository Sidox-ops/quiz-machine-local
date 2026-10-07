import 'package:ai103_quiz_ui/features/setup/data/environment_repository.dart';
import 'package:ai103_quiz_ui/features/setup/domain/setup_models.dart';

class FakeEnvironmentRepository implements EnvironmentRepository {
  static const readyDiagnostics = SystemDiagnostics(
    platform: 'macOS',
    architecture: 'arm64',
    ollamaInstalled: true,
    ollamaReachable: true,
    llmModel: 'gemma4:e4b-mlx',
    llmReady: true,
    embeddingModel: 'nomic-embed-text',
    embeddingReady: true,
    indexReady: true,
    indexedChunks: 33,
    freeDiskBytes: 20 * 1024 * 1024 * 1024,
    recommendedFreeBytes: 8 * 1024 * 1024 * 1024,
    diskReady: true,
  );

  @override
  Future<SystemDiagnostics> diagnostics() async => readyDiagnostics;

  @override
  Future<CorpusSummary> importCorpus({
    required String filename,
    required String jsonContent,
    required bool rightsConfirmed,
  }) async {
    return const CorpusSummary(
        title: 'Imported', language: 'en', chunkCount: 1);
  }

  @override
  Future<CorpusSummary> importMarkdownCorpus({
    required String filename,
    required String content,
    required bool rightsConfirmed,
  }) async {
    return const CorpusSummary(
      title: 'Imported Markdown',
      language: 'en',
      chunkCount: 1,
      certificationCode: 'AI-103',
      domain: 'Plan and manage an Azure AI solution',
    );
  }

  @override
  Future<List<CorpusSummary>> importMarkdownCorpora({
    required List<MarkdownCorpusDocument> files,
    required bool rightsConfirmed,
  }) async {
    return files
        .map(
          (_) => const CorpusSummary(
            title: 'Imported Markdown',
            language: 'en',
            chunkCount: 1,
            certificationCode: 'AI-103',
            domain: 'Plan and manage an Azure AI solution',
          ),
        )
        .toList(growable: false);
  }

  @override
  Future<CorpusSummary> validateMarkdownCorpus({
    required String filename,
    required String content,
    required bool rightsConfirmed,
  }) async {
    return const CorpusSummary(
      title: 'Imported Markdown',
      language: 'en',
      chunkCount: 1,
      certificationCode: 'AI-103',
      domain: 'Plan and manage an Azure AI solution',
    );
  }

  @override
  Future<SystemDiagnostics> prepare(SetupProgress onProgress) async {
    onProgress(const SetupStatus(status: 'completed', message: 'Ready.'));
    return readyDiagnostics;
  }
}
