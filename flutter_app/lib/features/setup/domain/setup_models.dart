import 'package:flutter/foundation.dart';

@immutable
class LocalModelInfo {
  const LocalModelInfo({
    required this.name,
    required this.size,
    required this.compatible,
    required this.compatibilityReason,
    this.digest = '',
    this.family = '',
    this.parameterSize = '',
    this.quantizationLevel = '',
    this.capabilities = const [],
    this.contextLength,
    this.license = '',
    this.estimatedMemoryBytes = 0,
    this.fitsMemory,
    this.probeStatus = 'not_run',
    this.probeDurationMs,
    this.probeError = '',
    this.selected = false,
    this.recommended = false,
  });

  final String name;
  final String digest;
  final int size;
  final String family;
  final String parameterSize;
  final String quantizationLevel;
  final List<String> capabilities;
  final int? contextLength;
  final String license;
  final int estimatedMemoryBytes;
  final bool? fitsMemory;
  final String probeStatus;
  final int? probeDurationMs;
  final String probeError;
  final bool compatible;
  final String compatibilityReason;
  final bool selected;
  final bool recommended;

  double get sizeGb => size / (1024 * 1024 * 1024);
  double get estimatedMemoryGb => estimatedMemoryBytes / (1024 * 1024 * 1024);

  String get summary {
    final parts = <String>[
      if (parameterSize.isNotEmpty) parameterSize,
      if (quantizationLevel.isNotEmpty) quantizationLevel,
      if (size > 0) '${sizeGb.toStringAsFixed(1)} GB',
      if (estimatedMemoryBytes > 0)
        '~${estimatedMemoryGb.toStringAsFixed(1)} GB memory',
      if (probeStatus == 'passed' && probeDurationMs != null)
        'JSON test ${(probeDurationMs! / 1000).toStringAsFixed(1)} s',
    ];
    return parts.isEmpty ? compatibilityReason : parts.join(' • ');
  }

  factory LocalModelInfo.fromJson(Map<String, dynamic> json) {
    final rawCapabilities = json['capabilities'];
    return LocalModelInfo(
      name: json['name']?.toString() ?? '',
      digest: json['digest']?.toString() ?? '',
      size: (json['size'] as num?)?.toInt() ?? 0,
      family: json['family']?.toString() ?? '',
      parameterSize: json['parameter_size']?.toString() ?? '',
      quantizationLevel: json['quantization_level']?.toString() ?? '',
      capabilities: rawCapabilities is List
          ? rawCapabilities.map((value) => value.toString()).toList()
          : const [],
      contextLength: (json['context_length'] as num?)?.toInt(),
      license: json['license']?.toString() ?? '',
      estimatedMemoryBytes:
          (json['estimated_memory_bytes'] as num?)?.toInt() ?? 0,
      fitsMemory: json['fits_memory'] as bool?,
      probeStatus: json['probe_status']?.toString() ?? 'not_run',
      probeDurationMs: (json['probe_duration_ms'] as num?)?.toInt(),
      probeError: json['probe_error']?.toString() ?? '',
      compatible: json['compatible'] == true,
      compatibilityReason:
          json['compatibility_reason']?.toString() ?? 'Compatibility unknown.',
      selected: json['selected'] == true,
      recommended: json['recommended'] == true,
    );
  }
}

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
    this.knowledgeCheckCompleted = false,
    required this.freeDiskBytes,
    required this.recommendedFreeBytes,
    required this.diskReady,
    this.ollamaModels = const [],
    this.recommendedLlmModel = '',
    this.modelSelectionLocked = false,
    this.physicalMemoryBytes = 0,
    this.modelRecommendationReason = '',
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
  final bool knowledgeCheckCompleted;
  final int freeDiskBytes;
  final int recommendedFreeBytes;
  final bool diskReady;
  final List<LocalModelInfo> ollamaModels;
  final String recommendedLlmModel;
  final bool modelSelectionLocked;
  final int physicalMemoryBytes;
  final String modelRecommendationReason;

  bool get ready =>
      ollamaInstalled &&
      ollamaReachable &&
      llmReady &&
      (usesMicrosoftLearn
          ? knowledgeReady &&
              knowledgeCheckCompleted &&
              (knowledgeProvider != 'hybrid' || embeddingReady && indexReady)
          : embeddingReady && indexReady);

  bool get usesMicrosoftLearn =>
      knowledgeProvider == 'microsoft_learn_mcp' ||
      knowledgeProvider == 'hybrid';

  double get freeDiskGb => freeDiskBytes / (1024 * 1024 * 1024);

  List<LocalModelInfo> get compatibleModels =>
      ollamaModels.where((model) => model.compatible).toList(growable: false);

  factory SystemDiagnostics.fromJson(Map<String, dynamic> json) {
    final rawModels = json['ollama_models'];
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
      knowledgeCheckCompleted: json['knowledge_check_completed'] == true,
      freeDiskBytes: (json['free_disk_bytes'] as num?)?.toInt() ?? 0,
      recommendedFreeBytes:
          (json['recommended_free_bytes'] as num?)?.toInt() ?? 0,
      diskReady: json['disk_ready'] == true,
      ollamaModels: rawModels is List
          ? rawModels
              .whereType<Map>()
              .map(
                (item) =>
                    LocalModelInfo.fromJson(Map<String, dynamic>.from(item)),
              )
              .toList(growable: false)
          : const [],
      recommendedLlmModel: json['recommended_llm_model']?.toString() ?? '',
      modelSelectionLocked: json['model_selection_locked'] == true,
      physicalMemoryBytes:
          (json['physical_memory_bytes'] as num?)?.toInt() ?? 0,
      modelRecommendationReason:
          json['model_recommendation_reason']?.toString() ?? '',
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
