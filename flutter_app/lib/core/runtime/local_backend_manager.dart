import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:math';

import 'package:http/http.dart' as http;
import 'package:path_provider/path_provider.dart';

class BackendSession {
  const BackendSession({
    required this.baseUrl,
    required this.token,
    required this.applicationDataPath,
    this.process,
  });

  final String baseUrl;
  final String token;
  final String applicationDataPath;
  final Process? process;

  void stop() => process?.kill();
}

abstract final class LocalBackendManager {
  static Future<BackendSession> start() async {
    final appData = await getApplicationSupportDirectory();
    final executable = _bundledBackend();
    if (executable == null || !executable.existsSync()) {
      return BackendSession(
        baseUrl: 'http://127.0.0.1:8000',
        token: '',
        applicationDataPath: appData.path,
      );
    }

    final port = 49152 + Random.secure().nextInt(16383);
    final token = List.generate(
      32,
      (_) => Random.secure().nextInt(256),
    ).map((byte) => byte.toRadixString(16).padLeft(2, '0')).join();
    final corpusDirectory =
        Directory('${appData.path}${Platform.pathSeparator}corpora');
    final storageDirectory =
        Directory('${appData.path}${Platform.pathSeparator}storage');
    corpusDirectory.createSync(recursive: true);
    storageDirectory.createSync(recursive: true);

    final process = await Process.start(
      executable.path,
      const [],
      environment: {
        ...Platform.environment,
        'AI103_BACKEND_PORT': '$port',
        'AI103_API_TOKEN': token,
        'AI103_USER_DATA_DIR': corpusDirectory.path,
        'AI103_STORAGE_DIR': storageDirectory.path,
      },
      mode: ProcessStartMode.normal,
    );
    final backendError = StringBuffer();
    process.stdout.transform(utf8.decoder).listen((_) {});
    process.stderr.transform(utf8.decoder).listen(backendError.write);
    final session = BackendSession(
      baseUrl: 'http://127.0.0.1:$port',
      token: token,
      applicationDataPath: appData.path,
      process: process,
    );
    await _waitUntilListening(session, backendError);
    return session;
  }

  static File? _bundledBackend() {
    final appExecutable = File(Platform.resolvedExecutable);
    if (Platform.isMacOS) {
      final contents = appExecutable.parent.parent;
      return File('${contents.path}/Resources/backend/quiz_backend');
    }
    if (Platform.isWindows) {
      return File('${appExecutable.parent.path}/backend/quiz_backend.exe');
    }
    return null;
  }

  static Future<void> _waitUntilListening(
    BackendSession session,
    StringBuffer backendError,
  ) async {
    int? exitCode;
    session.process?.exitCode.then((value) => exitCode = value);
    final client = http.Client();
    try {
      for (var attempt = 0; attempt < 40; attempt++) {
        await Future<void>.delayed(const Duration(milliseconds: 250));
        try {
          final response = await client.get(
            Uri.parse('${session.baseUrl}/system/diagnostics'),
            headers: {'Authorization': 'Bearer ${session.token}'},
          ).timeout(const Duration(seconds: 2));
          if (response.statusCode == 200) return;
        } catch (_) {
          // The backend is still starting.
        }
      }
    } finally {
      client.close();
    }
    session.stop();
    final detail = backendError.toString().trim();
    throw StateError(
      exitCode == null
          ? 'The local quiz engine did not answer in time.'
          : 'The local quiz engine stopped with code $exitCode.'
              '${detail.isEmpty ? '' : ' $detail'}',
    );
  }
}

class AcceptanceStore {
  AcceptanceStore([this.applicationDataPath]);

  static const currentVersion = '2026-09-07';

  final String? applicationDataPath;

  File get _file => File(
        '${_dataDirectory().path}${Platform.pathSeparator}accepted-terms.json',
      );

  bool isAccepted() {
    try {
      final payload =
          jsonDecode(_file.readAsStringSync()) as Map<String, dynamic>;
      return payload['version'] == currentVersion;
    } catch (_) {
      return false;
    }
  }

  void accept() {
    _file.parent.createSync(recursive: true);
    _file.writeAsStringSync(
      jsonEncode({
        'version': currentVersion,
        'accepted_at': DateTime.now().toUtc().toIso8601String(),
      }),
      flush: true,
    );
  }

  Directory _dataDirectory() {
    if (applicationDataPath != null) return Directory(applicationDataPath!);
    if (Platform.isMacOS) {
      return Directory(
        '${Platform.environment['HOME']}/Library/Application Support/Quiz Machine',
      );
    }
    if (Platform.isWindows) {
      final base = Platform.environment['APPDATA'] ??
          File(Platform.resolvedExecutable).parent.path;
      return Directory('$base${Platform.pathSeparator}Quiz Machine');
    }
    return Directory(
        '${Platform.environment['HOME']}/.local/share/quiz-machine');
  }
}
