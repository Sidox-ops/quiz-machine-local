import 'package:flutter/foundation.dart';

@immutable
class SystemDiagnostics {
  const SystemDiagnostics({
    required this.platform,
    required this.architecture,
    required this.ollamaInstalled,
    required this.ollamaReachable,
    required this.llmModel,
    required this.llmReady,
    required this.embeddingModel,
    required this.embeddingReady,
    required this.indexReady,
    required this.indexedChunks,
    this.knowledgeProvider = 'local',
    this.knowledgeReady = false,
    required this.freeDiskBytes,
    required this.recommendedFreeBytes,
    required this.diskReady,
  });

  final String platform;
  final String architecture;
  final bool ollamaInstalled;
  final bool ollamaReachable;
  final String llmModel;
  final bool llmReady;
  final String embeddingModel;
  final bool embeddingReady;
  final bool indexReady;
  final int indexedChunks;
  final String knowledgeProvider;
  final bool knowledgeReady;
  final int freeDiskBytes;
  final int recommendedFreeBytes;
  final bool diskReady;

  bool get ready =>
      ollamaInstalled &&
      ollamaReachable &&
      llmReady &&
      (usesMicrosoftLearn
          ? knowledgeReady &&
              (knowledgeProvider != 'hybrid' || embeddingReady && indexReady)
          : embeddingReady && indexReady);

  bool get usesMicrosoftLearn =>
      knowledgeProvider == 'microsoft_learn_mcp' ||
      knowledgeProvider == 'hybrid';

  double get freeDiskGb => freeDiskBytes / (1024 * 1024 * 1024);

  factory SystemDiagnostics.fromJson(Map<String, dynamic> json) {
    return SystemDiagnostics(
      platform: json['platform']?.toString() ?? 'Unknown',
      architecture: json['architecture']?.toString() ?? 'Unknown',
      ollamaInstalled: json['ollama_installed'] == true,
      ollamaReachable: json['ollama_reachable'] == true,
      llmModel: json['llm_model']?.toString() ?? '',
      llmReady: json['llm_ready'] == true,
      embeddingModel: json['embedding_model']?.toString() ?? '',
      embeddingReady: json['embedding_ready'] == true,
      indexReady: json['index_ready'] == true,
      indexedChunks: (json['indexed_chunks'] as num?)?.toInt() ?? 0,
      knowledgeProvider: json['knowledge_provider']?.toString() ?? 'local',
      knowledgeReady: json['knowledge_ready'] == true,
      freeDiskBytes: (json['free_disk_bytes'] as num?)?.toInt() ?? 0,
      recommendedFreeBytes:
          (json['recommended_free_bytes'] as num?)?.toInt() ?? 0,
      diskReady: json['disk_ready'] == true,
    );
  }
}

@immutable
class SetupStatus {
  const SetupStatus({required this.status, required this.message});

  final String status;
  final String message;

  bool get completed => status == 'completed';
  bool get failed => status == 'failed';

  factory SetupStatus.fromJson(Map<String, dynamic> json) {
    return SetupStatus(
      status: json['status']?.toString() ?? 'idle',
      message: json['message']?.toString() ?? '',
    );
  }
}

@immutable
class CorpusSummary {
  const CorpusSummary({
    required this.title,
    required this.language,
    required this.chunkCount,
    this.documentId,
    this.certificationCode,
    this.domain,
    this.sourceUrl,
  });

  final String title;
  final String language;
  final int chunkCount;
  final String? documentId;
  final String? certificationCode;
  final String? domain;
  final String? sourceUrl;

  factory CorpusSummary.fromJson(Map<String, dynamic> json) {
    return CorpusSummary(
      title: json['title']?.toString() ?? 'Untitled corpus',
      language: json['language']?.toString() ?? 'unspecified',
      chunkCount: (json['chunk_count'] as num?)?.toInt() ?? 0,
      documentId: json['document_id']?.toString(),
      certificationCode: json['certification_code']?.toString(),
      domain: json['domain']?.toString(),
      sourceUrl: json['source_url']?.toString(),
    );
  }
}
