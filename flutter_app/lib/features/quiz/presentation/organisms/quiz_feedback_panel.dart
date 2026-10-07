import 'package:flutter/material.dart';

import '../../../../core/design_system/foundations/app_tokens.dart';
import '../../domain/quiz_models.dart';

class QuizFeedbackPanel extends StatelessWidget {
  const QuizFeedbackPanel({
    required this.question,
    required this.result,
    required this.isLastQuestion,
    required this.onNext,
    super.key,
  });

  final QuizQuestion question;
  final QuizAnswerResult result;
  final bool isLastQuestion;
  final VoidCallback onNext;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final semantic = context.semanticColors;
    final statusColor = result.correct ? semantic.success : scheme.error;
    final statusContainer =
        result.correct ? semantic.successContainer : scheme.errorContainer;
    final onStatusContainer =
        result.correct ? semantic.onSuccessContainer : scheme.onErrorContainer;

    return Semantics(
      liveRegion: true,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          const Divider(),
          const SizedBox(height: AppSpacing.lg),
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              DecoratedBox(
                decoration: BoxDecoration(
                  color: statusContainer,
                  borderRadius: AppRadii.control,
                ),
                child: SizedBox.square(
                  dimension: 40,
                  child: Icon(
                    result.correct ? Icons.check : Icons.close,
                    color: statusColor,
                  ),
                ),
              ),
              const SizedBox(width: AppSpacing.sm),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      result.correct ? 'Correct' : 'Review this one',
                      style: Theme.of(context).textTheme.titleLarge?.copyWith(
                            color: onStatusContainer,
                          ),
                    ),
                    if (!result.correct)
                      Text(
                        'Correct answer: ${_labelFor(result.correctOptionId)} — '
                        '${_textFor(result.correctOptionId)}',
                        style: Theme.of(context).textTheme.labelLarge,
                      ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: AppSpacing.md),
          Text(result.explanation,
              style: Theme.of(context).textTheme.bodyLarge),
          if (result.decisiveClue.isNotEmpty) ...[
            const SizedBox(height: AppSpacing.md),
            _TeachingBlock(
              icon: Icons.filter_alt_outlined,
              title: 'What mattered',
              body: result.decisiveClue,
            ),
          ],
          if (result.learningRule.isNotEmpty) ...[
            const SizedBox(height: AppSpacing.sm),
            _TeachingBlock(
              icon: Icons.psychology_alt_outlined,
              title: 'Rule to remember',
              body: result.learningRule,
            ),
          ],
          if (!result.correct && result.selectedOptionFeedback.isNotEmpty) ...[
            const SizedBox(height: AppSpacing.sm),
            _TeachingBlock(
              icon: Icons.compare_arrows_outlined,
              title: 'Why your choice misses',
              body: result.selectedOptionFeedback,
            ),
          ],
          if (result.takeaway.isNotEmpty) ...[
            const SizedBox(height: AppSpacing.sm),
            _TeachingBlock(
              icon: Icons.bookmark_outline,
              title: 'Takeaway',
              body: result.takeaway,
            ),
          ],
          if (result.nextFocus case final nextFocus?) ...[
            const SizedBox(height: AppSpacing.sm),
            Text(
              'Next learning focus: $nextFocus',
              style: Theme.of(context).textTheme.labelLarge,
            ),
          ],
          const SizedBox(height: AppSpacing.sm),
          ExpansionTile(
            tilePadding: EdgeInsets.zero,
            childrenPadding: const EdgeInsets.only(bottom: AppSpacing.sm),
            shape: const Border(),
            collapsedShape: const Border(),
            title: const Text('Review all options'),
            children: result.optionExplanations
                .map(
                  (item) => Padding(
                    padding: const EdgeInsets.only(bottom: AppSpacing.sm),
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        SizedBox(
                          width: 28,
                          child: Text(
                            _labelFor(item.optionId),
                            style: Theme.of(context).textTheme.labelLarge,
                          ),
                        ),
                        Expanded(child: Text(item.explanation)),
                      ],
                    ),
                  ),
                )
                .toList(growable: false),
          ),
          if (result.sourceUrls.isNotEmpty)
            ExpansionTile(
              tilePadding: EdgeInsets.zero,
              childrenPadding: const EdgeInsets.only(bottom: AppSpacing.sm),
              shape: const Border(),
              collapsedShape: const Border(),
              title: const Text('Official Microsoft Learn sources'),
              children: result.sourceUrls
                  .map(
                    (url) => Padding(
                      padding: const EdgeInsets.only(bottom: AppSpacing.sm),
                      child: SelectableText(url),
                    ),
                  )
                  .toList(growable: false),
            ),
          const SizedBox(height: AppSpacing.md),
          Align(
            alignment: Alignment.centerRight,
            child: FilledButton.icon(
              onPressed: onNext,
              icon: Icon(
                  isLastQuestion ? Icons.flag_outlined : Icons.arrow_forward),
              label: Text(isLastQuestion ? 'Finish session' : 'Next question'),
            ),
          ),
        ],
      ),
    );
  }

  String _labelFor(String optionId) {
    final index =
        question.options.indexWhere((option) => option.id == optionId);
    return index < 0 ? '?' : String.fromCharCode(65 + index);
  }

  String _textFor(String optionId) {
    final index =
        question.options.indexWhere((option) => option.id == optionId);
    return index < 0 ? 'Unknown option' : question.options[index].text;
  }
}

class _TeachingBlock extends StatelessWidget {
  const _TeachingBlock({
    required this.icon,
    required this.title,
    required this.body,
  });

  final IconData icon;
  final String title;
  final String body;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return DecoratedBox(
      decoration: BoxDecoration(
        color: scheme.surfaceContainerLow,
        borderRadius: AppRadii.control,
        border: Border.all(color: scheme.outlineVariant),
      ),
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.sm),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Icon(icon, size: 20, color: scheme.primary),
            const SizedBox(width: AppSpacing.sm),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(title, style: Theme.of(context).textTheme.labelLarge),
                  const SizedBox(height: AppSpacing.xs),
                  Text(body),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
