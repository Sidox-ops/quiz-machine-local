import 'package:flutter/material.dart';

import '../../../../core/design_system/atoms/app_brand_mark.dart';
import '../../../../core/design_system/foundations/app_tokens.dart';
import '../../../../core/design_system/molecules/score_summary.dart';
import '../../data/quiz_repository.dart';
import '../../../setup/data/environment_repository.dart';
import '../../../setup/presentation/corpus_import_dialog.dart';
import '../organisms/generation_panel.dart';
import '../organisms/quiz_error_banner.dart';
import '../organisms/quiz_question_panel.dart';
import '../organisms/quiz_setup_panel.dart';
import '../organisms/session_state_panels.dart';
import 'progress_dashboard_page.dart';
import '../templates/quiz_workspace_template.dart';
import '../view_models/quiz_view_model.dart';

class QuizPage extends StatefulWidget {
  const QuizPage({
    required this.repository,
    required this.themeMode,
    required this.onThemeModeChanged,
    this.environmentRepository,
    super.key,
  });

  final QuizRepository repository;
  final ThemeMode themeMode;
  final ValueChanged<ThemeMode> onThemeModeChanged;
  final EnvironmentRepository? environmentRepository;

  @override
  State<QuizPage> createState() => _QuizPageState();
}

class _QuizPageState extends State<QuizPage> {
  late final QuizViewModel _viewModel;

  @override
  void initState() {
    super.initState();
    _viewModel = QuizViewModel(widget.repository)..initialize();
  }

  @override
  void dispose() {
    _viewModel.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _viewModel,
      builder: (context, _) {
        final isNarrow = MediaQuery.sizeOf(context).width < 960;
        return Scaffold(
          appBar: AppBar(
            titleSpacing: AppSpacing.md,
            title: Row(
              children: [
                const AppBrandMark(),
                const SizedBox(width: AppSpacing.sm),
                Flexible(
                  child: Text(
                    isNarrow
                        ? _viewModel.selectedCertificationCode
                        : '${_viewModel.selectedCertificationCode} Practice',
                    overflow: TextOverflow.ellipsis,
                    style: Theme.of(context).textTheme.titleLarge,
                  ),
                ),
              ],
            ),
            actions: [
              IconButton(
                onPressed: _showProgressDashboard,
                tooltip: 'Learning dashboard',
                icon: const Icon(Icons.insights_outlined),
              ),
              if (widget.environmentRepository != null)
                IconButton(
                  onPressed: _importCorpus,
                  tooltip: 'Import corpus',
                  icon: const Icon(Icons.folder_open_outlined),
                ),
              if (!isNarrow)
                Padding(
                  padding:
                      const EdgeInsets.symmetric(horizontal: AppSpacing.sm),
                  child: Center(
                    child: ScoreSummary(
                      progress: _viewModel.progress,
                      compact: true,
                    ),
                  ),
                ),
              if (isNarrow && _viewModel.stage == QuizStage.active)
                IconButton(
                  onPressed: _showSettings,
                  tooltip: 'Session settings',
                  icon: const Icon(Icons.tune),
                ),
              IconButton(
                onPressed: _toggleTheme,
                tooltip: 'Toggle theme',
                icon: Icon(
                  Theme.of(context).brightness == Brightness.dark
                      ? Icons.light_mode_outlined
                      : Icons.dark_mode_outlined,
                ),
              ),
              IconButton(
                onPressed: _showAbout,
                tooltip: 'About Quiz Machine',
                icon: const Icon(Icons.info_outline),
              ),
              const SizedBox(width: AppSpacing.xs),
            ],
          ),
          body: QuizWorkspaceTemplate(
            setup: QuizSetupPanel(viewModel: _viewModel),
            content: _content(context),
            showSetupOnNarrow: _viewModel.stage == QuizStage.ready,
          ),
        );
      },
    );
  }

  Widget _content(BuildContext context) {
    final stateContent = switch (_viewModel.stage) {
      QuizStage.loading => const LoadingPanel(key: ValueKey('loading')),
      QuizStage.ready => ReadyPanel(
          key: const ValueKey('ready'),
          progress: _viewModel.progress,
        ),
      QuizStage.generating => GenerationPanel(
          key: const ValueKey('generating'),
          completed: _viewModel.generatedCount,
          total: _viewModel.generationTotal,
          attempts: _viewModel.generationAttempts,
          rejected: _viewModel.generationRejected,
          reused: _viewModel.generationReused,
          phase: _viewModel.generationPhase,
          corpusCompleted: _viewModel.corpusCompleted,
          corpusTotal: _viewModel.corpusTotal,
          corpusAttempts: _viewModel.corpusAttempts,
          corpusRetries: _viewModel.corpusRetries,
          message: _viewModel.generationMessage,
          cancelling: _viewModel.cancellingGeneration,
          onCancel: _viewModel.cancelGeneration,
        ),
      QuizStage.active => QuizQuestionPanel(
          key: ValueKey(_viewModel.currentQuestion?.questionId),
          viewModel: _viewModel,
        ),
      QuizStage.complete => CompletePanel(
          key: const ValueKey('complete'),
          progress: _viewModel.progress,
          onContinue: _viewModel.prepareNewQuiz,
        ),
    };

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        if (_viewModel.error != null) ...[
          QuizErrorBanner(
            message: _viewModel.error!,
            onDismiss: _viewModel.dismissError,
          ),
          const SizedBox(height: AppSpacing.lg),
        ],
        AnimatedSwitcher(
          duration: AppMotion.resolve(context, AppMotion.standard),
          switchInCurve: AppMotion.enter,
          switchOutCurve: AppMotion.exit,
          transitionBuilder: (child, animation) {
            final offset = Tween<Offset>(
              begin: const Offset(0, 0.025),
              end: Offset.zero,
            ).animate(animation);
            return FadeTransition(
              opacity: animation,
              child: SlideTransition(position: offset, child: child),
            );
          },
          child: stateContent,
        ),
      ],
    );
  }

  void _toggleTheme() {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    widget.onThemeModeChanged(isDark ? ThemeMode.light : ThemeMode.dark);
  }

  void _showProgressDashboard() {
    Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (context) => ProgressDashboardPage(viewModel: _viewModel),
      ),
    );
  }

  void _showAbout() {
    showAboutDialog(
      context: context,
      applicationName: 'Quiz Machine',
      applicationVersion: '0.1.0',
      applicationLegalese: 'Copyright 2026 Quiz Machine publisher.\n'
          'Independent educational tool. Not affiliated with Microsoft.',
      children: const [
        SizedBox(height: AppSpacing.sm),
        Text(
          'Runs locally with Ollama. Third-party package licences are '
          'available through the View licences button.',
        ),
      ],
    );
  }

  Future<void> _importCorpus() async {
    final repository = widget.environmentRepository;
    if (repository == null) return;
    final summary = await CorpusImportDialog.show(context, repository);
    if (!mounted || summary == null) return;
    await _viewModel.initialize();
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
          content:
              Text('${summary.title}: ${summary.chunkCount} chunks imported.')),
    );
  }

  void _showSettings() {
    showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      showDragHandle: true,
      builder: (sheetContext) {
        return SafeArea(
          child: AnimatedBuilder(
            animation: _viewModel,
            builder: (context, _) {
              return SingleChildScrollView(
                padding: EdgeInsets.fromLTRB(
                  AppSpacing.lg,
                  AppSpacing.sm,
                  AppSpacing.lg,
                  AppSpacing.lg + MediaQuery.viewInsetsOf(context).bottom,
                ),
                child: QuizSetupPanel(
                  viewModel: _viewModel,
                  onGenerate: () => Navigator.of(sheetContext).pop(),
                ),
              );
            },
          ),
        );
      },
    );
  }
}
