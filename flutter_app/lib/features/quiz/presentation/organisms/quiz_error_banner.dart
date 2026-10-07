import 'package:flutter/material.dart';

import '../../../../core/design_system/foundations/app_tokens.dart';

class QuizErrorBanner extends StatelessWidget {
  const QuizErrorBanner({
    required this.message,
    required this.onDismiss,
    super.key,
  });

  final String message;
  final VoidCallback onDismiss;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Semantics(
      liveRegion: true,
      child: DecoratedBox(
        decoration: BoxDecoration(
          color: scheme.errorContainer,
          borderRadius: AppRadii.control,
          border: Border.all(color: scheme.error),
        ),
        child: Padding(
          padding: const EdgeInsets.fromLTRB(16, 12, 8, 12),
          child: Row(
            children: [
              Icon(Icons.error_outline, color: scheme.onErrorContainer),
              const SizedBox(width: AppSpacing.sm),
              Expanded(
                child: Text(
                  message,
                  style: TextStyle(color: scheme.onErrorContainer),
                ),
              ),
              IconButton(
                onPressed: onDismiss,
                tooltip: 'Dismiss error',
                icon: const Icon(Icons.close),
                color: scheme.onErrorContainer,
              ),
            ],
          ),
        ),
      ),
    );
  }
}
