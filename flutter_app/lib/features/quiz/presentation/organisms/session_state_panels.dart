import 'package:flutter/material.dart';

import '../../../../core/design_system/foundations/app_tokens.dart';
import '../../../../core/design_system/molecules/score_summary.dart';
import '../../domain/quiz_models.dart';

class LoadingPanel extends StatelessWidget {
  const LoadingPanel({super.key});

  @override
  Widget build(BuildContext context) {
    return const Center(child: CircularProgressIndicator());
  }
}

class ReadyPanel extends StatelessWidget {
  const ReadyPanel({required this.progress, super.key});

  final QuizProgress progress;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 520),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              Icons.center_focus_strong_outlined,
              size: 40,
              color: Theme.of(context).colorScheme.primary,
            ),
            const SizedBox(height: AppSpacing.md),
            Text(
              progress.asked == 0
                  ? 'Ready for your first session'
                  : 'Ready to continue',
              textAlign: TextAlign.center,
              style: Theme.of(context).textTheme.headlineSmall,
            ),
          ],
        ),
      ),
    );
  }
}

class CompletePanel extends StatelessWidget {
  const CompletePanel({
    required this.progress,
    required this.onContinue,
    super.key,
  });

  final QuizProgress progress;
  final VoidCallback onContinue;

  @override
  Widget build(BuildContext context) {
    final semantic = context.semanticColors;
    return Center(
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 560),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Icon(Icons.check_circle_outline, size: 44, color: semantic.success),
            const SizedBox(height: AppSpacing.md),
            Text(
              'Session complete',
              textAlign: TextAlign.center,
              style: Theme.of(context).textTheme.headlineSmall,
            ),
            const SizedBox(height: AppSpacing.xl),
            ScoreSummary(progress: progress),
            const SizedBox(height: AppSpacing.xl),
            Align(
              child: FilledButton.icon(
                onPressed: onContinue,
                icon: const Icon(Icons.refresh),
                label: const Text('New session'),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
