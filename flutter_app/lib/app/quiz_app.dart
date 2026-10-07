import 'package:flutter/material.dart';

import '../core/design_system/theme/app_theme.dart';
import '../core/runtime/local_backend_manager.dart';
import '../features/quiz/data/quiz_api_service.dart';
import '../features/quiz/data/quiz_repository.dart';
import '../features/quiz/presentation/pages/quiz_page.dart';
import '../features/setup/data/environment_repository.dart';
import '../features/setup/presentation/onboarding_page.dart';

class Ai103QuizApp extends StatefulWidget {
  const Ai103QuizApp({
    this.repository,
    this.environmentRepository,
    this.backendSession,
    this.acceptanceStore,
    super.key,
  });

  final QuizRepository? repository;
  final EnvironmentRepository? environmentRepository;
  final BackendSession? backendSession;
  final AcceptanceStore? acceptanceStore;

  @override
  State<Ai103QuizApp> createState() => _Ai103QuizAppState();
}

class _Ai103QuizAppState extends State<Ai103QuizApp> {
  late final QuizRepository _repository;
  EnvironmentRepository? _environmentRepository;
  late final AcceptanceStore _acceptanceStore;
  ThemeMode _themeMode = ThemeMode.system;
  bool _onboardingComplete = false;

  @override
  void initState() {
    super.initState();
    _acceptanceStore = widget.acceptanceStore ??
        AcceptanceStore(widget.backendSession?.applicationDataPath);
    if (widget.repository != null) {
      _repository = widget.repository!;
      _environmentRepository = widget.environmentRepository;
      _onboardingComplete = _environmentRepository == null;
    } else {
      final service = QuizApiService(
        baseUrl: widget.backendSession?.baseUrl ?? 'http://127.0.0.1:8000',
        token: widget.backendSession?.token ?? '',
      );
      _repository = RemoteQuizRepository(service);
      _environmentRepository = RemoteEnvironmentRepository(service);
    }
  }

  @override
  void dispose() {
    widget.backendSession?.stop();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      title: 'Microsoft Certification Practice',
      theme: AppTheme.light,
      darkTheme: AppTheme.dark,
      themeMode: _themeMode,
      home: !_onboardingComplete && _environmentRepository != null
          ? OnboardingPage(
              repository: _environmentRepository!,
              acceptanceStore: _acceptanceStore,
              onCompleted: () => setState(() => _onboardingComplete = true),
            )
          : QuizPage(
              repository: _repository,
              environmentRepository: _environmentRepository,
              themeMode: _themeMode,
              onThemeModeChanged: (value) => setState(() => _themeMode = value),
            ),
    );
  }
}
