import 'dart:convert';

import 'package:http/http.dart' as http;

class QuizApiException implements Exception {
  const QuizApiException(this.message, {this.issues = const []});

  final String message;
  final List<CorpusImportIssue> issues;

  @override
  String toString() => message;
}

class CorpusImportIssue {
  const CorpusImportIssue({
    required this.message,
    this.field,
    this.line,
    this.hint,
  });

  final String message;
  final String? field;
  final int? line;
  final String? hint;

  factory CorpusImportIssue.fromJson(Map<String, dynamic> json) {
    return CorpusImportIssue(
      message: json['message']?.toString() ?? 'Invalid corpus file.',
      field: json['field']?.toString(),
      line: (json['line'] as num?)?.toInt(),
      hint: json['hint']?.toString(),
    );
  }
}

class QuizApiService {
  QuizApiService({
    http.Client? client,
    this.baseUrl = 'http://127.0.0.1:8000',
    this.token = '',
  }) : _client = client ?? http.Client();

  final http.Client _client;
  final String baseUrl;
  final String token;

  Map<String, String> get _headers => {
        'Content-Type': 'application/json',
        if (token.isNotEmpty) 'Authorization': 'Bearer $token',
      };

  Future<Map<String, dynamic>> startBatch({
    required String certificationCode,
    required int count,
    required String mode,
    required String difficulty,
    required String questionType,
    String? domain,
    String? chapterId,
  }) {
    return _post(
      '/quiz/batch',
      body: {
        'count': count,
        'certification_code': certificationCode,
        'mode': mode,
        'difficulty': difficulty,
        'question_type': questionType,
        'domain': domain,
        'chapter_id': chapterId,
      },
    );
  }

  Future<Map<String, dynamic>> batchStatus(String jobId) {
    return _get('/quiz/batch/$jobId');
  }

  Future<Map<String, dynamic>> cancelBatch(String jobId) {
    return _post('/quiz/batch/$jobId/cancel', body: const {});
  }

  Future<Map<String, dynamic>> answer(String questionId, String option,
      {double? elapsedSeconds}) {
    return _post(
      '/quiz/answer',
      body: {
        'question_id': questionId,
        'selected_option_id': option,
        if (elapsedSeconds != null) 'elapsed_seconds': elapsedSeconds,
      },
    );
  }

  Future<Map<String, dynamic>> progress({String? certificationCode}) {
    final query = certificationCode == null
        ? ''
        : '?certification_code=${Uri.encodeQueryComponent(certificationCode)}';
    return _get('/progress$query');
  }

  Future<Map<String, dynamic>> resetProgress({
    required String scope,
    String? certificationCode,
  }) {
    return _post(
      '/progress/reset',
      body: {
        'scope': scope,
        if (certificationCode != null) 'certification_code': certificationCode,
      },
    );
  }

  Future<Map<String, dynamic>> catalog({String? certificationCode}) {
    final query = certificationCode == null
        ? ''
        : '?certification_code=${Uri.encodeQueryComponent(certificationCode)}';
    return _get('/catalog$query');
  }

  Future<Map<String, dynamic>> diagnostics() => _get('/system/diagnostics');

  Future<Map<String, dynamic>> startSetup() =>
      _post('/system/setup', body: const {});

  Future<Map<String, dynamic>> setupStatus() => _get('/system/setup');

  Future<Map<String, dynamic>> importCorpus({
    required String filename,
    required Map<String, dynamic> corpus,
    required bool rightsConfirmed,
  }) {
    return _post(
      '/corpus/import',
      body: {
        'filename': filename,
        'corpus': corpus,
        'rights_confirmed': rightsConfirmed,
      },
    );
  }

  Future<Map<String, dynamic>> validateMarkdownCorpus({
    required String filename,
    required String content,
    required bool rightsConfirmed,
  }) {
    return _post(
      '/corpus/markdown/validate',
      body: {
        'filename': filename,
        'content': content,
        'rights_confirmed': rightsConfirmed,
      },
    );
  }

  Future<Map<String, dynamic>> importMarkdownCorpus({
    required String filename,
    required String content,
    required bool rightsConfirmed,
  }) {
    return _post(
      '/corpus/markdown/import',
      body: {
        'filename': filename,
        'content': content,
        'rights_confirmed': rightsConfirmed,
      },
    );
  }

  Future<Map<String, dynamic>> importMarkdownCorpora({
    required List<Map<String, String>> files,
    required bool rightsConfirmed,
  }) {
    return _post(
      '/corpus/markdown/import-batch',
      body: {
        'files': files,
        'rights_confirmed': rightsConfirmed,
      },
    );
  }

  Future<Map<String, dynamic>> _get(String path) async {
    final response = await _client.get(
      Uri.parse('$baseUrl$path'),
      headers: _headers,
    );
    return _decode(response);
  }

  Future<Map<String, dynamic>> _post(
    String path, {
    required Map<String, dynamic> body,
  }) async {
    final response = await _client.post(
      Uri.parse('$baseUrl$path'),
      headers: _headers,
      body: jsonEncode(body),
    );
    return _decode(response);
  }

  Map<String, dynamic> _decode(http.Response response) {
    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw _exception(response);
    }
    return jsonDecode(response.body) as Map<String, dynamic>;
  }

  QuizApiException _exception(http.Response response) {
    try {
      final body = jsonDecode(response.body) as Map<String, dynamic>;
      final detail = body['detail'];
      if (detail is Map<String, dynamic>) {
        final rawIssues = detail['issues'];
        final issues = rawIssues is List
            ? rawIssues
                .whereType<Map>()
                .map((item) => CorpusImportIssue.fromJson(
                      Map<String, dynamic>.from(item),
                    ))
                .toList(growable: false)
            : const <CorpusImportIssue>[];
        return QuizApiException(
          detail['message']?.toString() ?? 'HTTP ${response.statusCode}',
          issues: issues,
        );
      }
      return QuizApiException(
        detail?.toString() ?? 'HTTP ${response.statusCode}',
      );
    } catch (_) {
      return QuizApiException('HTTP ${response.statusCode}');
    }
  }

  void close() => _client.close();
}
