import 'package:flutter/material.dart';

import '../../../../core/design_system/foundations/app_tokens.dart';
import '../../domain/quiz_models.dart';

enum AnswerOptionState { idle, selected, correct, incorrect, muted }

class AnswerOptionTile extends StatelessWidget {
  const AnswerOptionTile({
    required this.option,
    required this.presentationLabel,
    required this.state,
    required this.onPressed,
    super.key,
  });

  final QuizOption option;
  final String presentationLabel;
  final AnswerOptionState state;
  final VoidCallback? onPressed;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final semantic = context.semanticColors;
    final isSelected = state == AnswerOptionState.selected;
    final isCorrect = state == AnswerOptionState.correct;
    final isIncorrect = state == AnswerOptionState.incorrect;

    final background = switch (state) {
      AnswerOptionState.selected => scheme.primaryContainer,
      AnswerOptionState.correct => semantic.successContainer,
      AnswerOptionState.incorrect => scheme.errorContainer,
      _ => scheme.surfaceContainerLowest,
    };
    final border = switch (state) {
      AnswerOptionState.selected => scheme.primary,
      AnswerOptionState.correct => semantic.success,
      AnswerOptionState.incorrect => scheme.error,
      _ => scheme.outlineVariant,
    };
    final foreground = switch (state) {
      AnswerOptionState.selected => scheme.onPrimaryContainer,
      AnswerOptionState.correct => semantic.onSuccessContainer,
      AnswerOptionState.incorrect => scheme.onErrorContainer,
      _ => scheme.onSurface,
    };
    final markerBackground =
        state == AnswerOptionState.idle ? scheme.surfaceContainerHigh : border;
    final markerForeground =
        state == AnswerOptionState.idle ? scheme.onSurfaceVariant : foreground;

    return Semantics(
      button: onPressed != null,
      selected: isSelected,
      label: 'Option $presentationLabel. ${option.text}',
      child: AnimatedContainer(
        duration: AppMotion.resolve(context, AppMotion.fast),
        curve: AppMotion.enter,
        decoration: BoxDecoration(
          color: background,
          borderRadius: AppRadii.control,
          border: Border.all(
              color: border, width: state == AnswerOptionState.idle ? 1 : 2),
        ),
        child: Material(
          color: Colors.transparent,
          child: InkWell(
            onTap: onPressed,
            borderRadius: AppRadii.control,
            child: ConstrainedBox(
              constraints: const BoxConstraints(minHeight: 58),
              child: Padding(
                padding: const EdgeInsets.symmetric(
                  horizontal: AppSpacing.md,
                  vertical: AppSpacing.sm,
                ),
                child: Row(
                  children: [
                    AnimatedContainer(
                      duration: AppMotion.resolve(context, AppMotion.fast),
                      width: 32,
                      height: 32,
                      alignment: Alignment.center,
                      decoration: BoxDecoration(
                        color: markerBackground,
                        borderRadius: AppRadii.compact,
                      ),
                      child: isCorrect || isIncorrect
                          ? Icon(
                              isCorrect ? Icons.check : Icons.close,
                              size: 18,
                              color: isCorrect
                                  ? semantic.onSuccess
                                  : scheme.onError,
                            )
                          : Text(
                              presentationLabel,
                              style: Theme.of(context)
                                  .textTheme
                                  .labelLarge
                                  ?.copyWith(
                                    color: markerForeground,
                                  ),
                            ),
                    ),
                    const SizedBox(width: AppSpacing.sm),
                    Expanded(
                      child: Text(
                        option.text,
                        style: Theme.of(context).textTheme.bodyLarge?.copyWith(
                              color: foreground,
                              fontWeight: isSelected
                                  ? FontWeight.w600
                                  : FontWeight.w400,
                            ),
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
