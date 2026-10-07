import 'package:flutter/material.dart';

import '../../../../core/design_system/atoms/app_badge.dart';
import '../../../../core/design_system/foundations/app_tokens.dart';
import '../../domain/quiz_models.dart';

class QuizProgressHeader extends StatelessWidget {
  const QuizProgressHeader({
    required this.question,
    required this.index,
    required this.total,
    required this.progress,
    super.key,
  });

  final QuizQuestion question;
  final int index;
  final int total;
  final double progress;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Row(
          children: [
            Expanded(
              child: Text(
                'Question ${index + 1} of $total',
                style: Theme.of(context).textTheme.titleMedium,
              ),
            ),
            AppBadge(
              label: question.difficulty,
              icon: Icons.speed_outlined,
              emphasized: true,
            ),
          ],
        ),
        const SizedBox(height: AppSpacing.sm),
        Semantics(
          label: 'Quiz progress ${(progress * 100).round()} percent',
          child: LinearProgressIndicator(value: progress, minHeight: 6),
        ),
        const SizedBox(height: AppSpacing.md),
        Wrap(
          spacing: AppSpacing.xs,
          runSpacing: AppSpacing.xs,
          children: [
            if (question.questionType == QuizQuestionType.caseStudy)
              const AppBadge(
                label: 'Case study',
                icon: Icons.description_outlined,
                emphasized: true,
              ),
            AppBadge(label: question.domain, icon: Icons.account_tree_outlined),
            AppBadge(label: question.topic, icon: Icons.bookmark_outline),
          ],
        ),
      ],
    );
  }
}
