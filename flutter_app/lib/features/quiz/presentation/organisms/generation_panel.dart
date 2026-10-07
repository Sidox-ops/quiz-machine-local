import 'package:flutter/material.dart';

import '../../../../core/design_system/foundations/app_tokens.dart';

class GenerationPanel extends StatelessWidget {
  const GenerationPanel({
    required this.completed,
    required this.total,
    required this.attempts,
    required this.rejected,
    this.reused = 0,
    required this.phase,
    required this.corpusCompleted,
    required this.corpusTotal,
    required this.corpusAttempts,
    required this.corpusRetries,
    required this.message,
    required this.cancelling,
    required this.onCancel,
    super.key,
  });

  final int completed;
  final int total;
  final int attempts;
  final int rejected;
  final int reused;
  final String phase;
  final int corpusCompleted;
  final int corpusTotal;
  final int corpusAttempts;
  final int corpusRetries;
  final String message;
  final bool cancelling;
  final VoidCallback onCancel;

  @override
  Widget build(BuildContext context) {
    final preparingCorpus = phase == 'preparing_corpus';
    final progress = preparingCorpus
        ? (corpusTotal == 0 ? null : corpusCompleted / corpusTotal)
        : (total == 0 ? 0.0 : completed / total);
    return Center(
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 520),
        child: Padding(
          padding: const EdgeInsets.symmetric(vertical: AppSpacing.xxl),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Icon(
                Icons.hourglass_top,
                size: 34,
                color: Theme.of(context).colorScheme.primary,
              ),
              const SizedBox(height: AppSpacing.lg),
              Text(
                preparingCorpus
                    ? 'Preparing certification corpus'
                    : 'Building question set',
                textAlign: TextAlign.center,
                style: Theme.of(context).textTheme.headlineSmall,
              ),
              const SizedBox(height: AppSpacing.sm),
              Text(
                preparingCorpus
                    ? (corpusTotal == 0
                        ? 'Loading official blueprint'
                        : '$corpusCompleted of $corpusTotal objectives')
                    : '$completed of $total',
                textAlign: TextAlign.center,
                style: Theme.of(context).textTheme.titleMedium,
              ),
              const SizedBox(height: AppSpacing.lg),
              Semantics(
                label: preparingCorpus
                    ? 'Prepared $corpusCompleted of $corpusTotal objectives'
                    : 'Generated $completed of $total questions',
                child: LinearProgressIndicator(value: progress, minHeight: 8),
              ),
              const SizedBox(height: AppSpacing.md),
              Text(
                message,
                textAlign: TextAlign.center,
                style: Theme.of(context).textTheme.bodyMedium,
              ),
              const SizedBox(height: AppSpacing.xs),
              Text(
                preparingCorpus
                    ? '$corpusAttempts preparation attempt(s)'
                        '${corpusRetries == 0 ? '' : ' • $corpusRetries retried'}'
                    : '$reused reused from the validated bank • '
                        '$attempts candidates checked'
                        '${rejected == 0 ? '' : ' • $rejected rejected and retried'}',
                textAlign: TextAlign.center,
                style: Theme.of(context).textTheme.bodySmall,
              ),
              const SizedBox(height: AppSpacing.xs),
              Text(
                preparingCorpus
                    ? 'Microsoft Learn fills the canonical local corpus. Each question then uses a small evidence packet selected from its raw chunks.'
                    : 'Validated questions are kept in the local bank. Revision never waits for a model call.',
                textAlign: TextAlign.center,
                style: Theme.of(context).textTheme.bodySmall,
              ),
              const SizedBox(height: AppSpacing.lg),
              Align(
                child: TextButton.icon(
                  onPressed: cancelling ? null : onCancel,
                  icon: const Icon(Icons.stop_circle_outlined),
                  label:
                      Text(cancelling ? 'Cancelling...' : 'Cancel generation'),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
