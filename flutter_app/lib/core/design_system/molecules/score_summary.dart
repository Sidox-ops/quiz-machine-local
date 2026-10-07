import 'package:flutter/material.dart';

import '../../../features/quiz/domain/quiz_models.dart';
import '../foundations/app_tokens.dart';

class ScoreSummary extends StatelessWidget {
  const ScoreSummary({required this.progress, this.compact = false, super.key});

  final QuizProgress progress;
  final bool compact;

  @override
  Widget build(BuildContext context) {
    if (compact) {
      return Semantics(
        label:
            '${progress.correct} correct answers out of ${progress.asked}, ${progress.percent} percent',
        child: Text(
          progress.asked == 0
              ? 'No score'
              : '${progress.correct}/${progress.asked}  ${progress.percent}%',
          style: Theme.of(context).textTheme.labelLarge,
        ),
      );
    }

    return Row(
      children: [
        Expanded(
          child: _Metric(
            label: 'Answered',
            value: progress.asked.toString(),
          ),
        ),
        const SizedBox(width: AppSpacing.sm),
        Expanded(
          child: _Metric(
            label: 'Correct',
            value: progress.correct.toString(),
          ),
        ),
        const SizedBox(width: AppSpacing.sm),
        Expanded(
          child: _Metric(
            label: 'Accuracy',
            value: '${progress.percent}%',
          ),
        ),
      ],
    );
  }
}

class _Metric extends StatelessWidget {
  const _Metric({required this.label, required this.value});

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return DecoratedBox(
      decoration: BoxDecoration(
        color: scheme.surfaceContainerLow,
        borderRadius: AppRadii.control,
      ),
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.sm),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(label, style: Theme.of(context).textTheme.labelMedium),
            const SizedBox(height: AppSpacing.xxs),
            Text(value, style: Theme.of(context).textTheme.titleLarge),
          ],
        ),
      ),
    );
  }
}
