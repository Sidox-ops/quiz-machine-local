import 'dart:async';
import 'dart:convert';

import '../../quiz/data/quiz_api_service.dart';
import '../domain/setup_models.dart';

typedef SetupProgress = void Function(SetupStatus status);

abstract interface class EnvironmentRepository {
  Future<SystemDiagnostics> diagnostics();

  Future<SystemDiagnostics> prepare(SetupProgress onProgress);

  Future<CorpusSummary> importCorpus({
    required String filename,
    required String jsonContent,
    required bool rightsConfirmed,
  });

  Future<CorpusSummary> validateMarkdownCorpus({
    required String filename,
    required String content,
    required bool rightsConfirmed,
  });

  Future<CorpusSummary> importMarkdownCorpus({
    required String filename,
    required String content,
    required bool rightsConfirmed,
  });

  Future<List<CorpusSummary>> importMarkdownCorpora({
    required List<MarkdownCorpusDocument> files,
    required bool rightsConfirmed,
  });
}

class MarkdownCorpusDocument {
  const MarkdownCorpusDocument({required this.filename, required this.content});

  final String filename;
  final String content;
}

class RemoteEnvironmentRepository implements EnvironmentRepository {
  const RemoteEnvironmentRepository(this._service);

  final QuizApiService _service;

  @override
  Future<SystemDiagnostics> diagnostics() async {
    return SystemDiagnostics.fromJson(await _service.diagnostics());
  }

  @override
  Future<SystemDiagnostics> prepare(SetupProgress onProgress) async {
    await _service.startSetup();
    while (true) {
      final status = SetupStatus.fromJson(await _service.setupStatus());
      onProgress(status);
      if (status.failed) throw QuizApiException(status.message);
      if (status.completed) return diagnostics();
      await Future<void>.delayed(const Duration(milliseconds: 800));
    }
  }

  @override
  Future<CorpusSummary> importCorpus({
    required String filename,
    required String jsonContent,
    required bool rightsConfirmed,
  }) async {
    if (utf8.encode(jsonContent).length > 5 * 1024 * 1024) {
      throw const QuizApiException('The corpus exceeds the 5 MB import limit.');
    }
    final decoded = jsonDecode(jsonContent);
    if (decoded is! Map<String, dynamic>) {
      throw const QuizApiException('The JSON root must be an object.');
    }
    return CorpusSummary.fromJson(
      await _service.importCorpus(
        filename: filename,
        corpus: decoded,
        rightsConfirmed: rightsConfirmed,
      ),
    );
  }

  @override
  Future<CorpusSummary> validateMarkdownCorpus({
    required String filename,
    required String content,
    required bool rightsConfirmed,
  }) async {
    _checkMarkdownSize(content);
    return CorpusSummary.fromJson(
      await _service.validateMarkdownCorpus(
        filename: filename,
        content: content,
        rightsConfirmed: rightsConfirmed,
      ),
    );
  }

  @override
  Future<CorpusSummary> importMarkdownCorpus({
    required String filename,
    required String content,
    required bool rightsConfirmed,
  }) async {
    _checkMarkdownSize(content);
    return CorpusSummary.fromJson(
      await _service.importMarkdownCorpus(
        filename: filename,
        content: content,
        rightsConfirmed: rightsConfirmed,
      ),
    );
  }

  @override
  Future<List<CorpusSummary>> importMarkdownCorpora({
    required List<MarkdownCorpusDocument> files,
    required bool rightsConfirmed,
  }) async {
    for (final file in files) {
      _checkMarkdownSize(file.content);
    }
    final response = await _service.importMarkdownCorpora(
      files: files
          .map((file) => {
                'filename': file.filename,
                'content': file.content,
              })
          .toList(growable: false),
      rightsConfirmed: rightsConfirmed,
    );
    final values = response['files'];
    if (values is! List) {
      throw const QuizApiException('The import response is invalid.');
    }
    return values
        .whereType<Map>()
        .map((item) => CorpusSummary.fromJson(Map<String, dynamic>.from(item)))
        .toList(growable: false);
  }

  void _checkMarkdownSize(String content) {
    if (utf8.encode(content).length > 5 * 1024 * 1024) {
      throw const QuizApiException(
        'The corpus exceeds the 5 MB import limit.',
      );
    }
  }
}
