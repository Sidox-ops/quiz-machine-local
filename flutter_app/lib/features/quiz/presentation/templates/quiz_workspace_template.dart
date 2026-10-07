import 'package:flutter/material.dart';

import '../../../../core/design_system/foundations/app_tokens.dart';

class QuizWorkspaceTemplate extends StatelessWidget {
  const QuizWorkspaceTemplate({
    required this.setup,
    required this.content,
    required this.showSetupOnNarrow,
    super.key,
  });

  final Widget setup;
  final Widget content;
  final bool showSetupOnNarrow;

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final isWide = constraints.maxWidth >= 960;
        if (!isWide) {
          return _ScrollableRegion(
            padding: const EdgeInsets.all(AppSpacing.md),
            child: showSetupOnNarrow ? setup : content,
          );
        }

        final scheme = Theme.of(context).colorScheme;
        return Row(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            SizedBox(
              width: 350,
              child: DecoratedBox(
                decoration: BoxDecoration(
                  color: scheme.surfaceContainerLow,
                  border: Border(
                    right: BorderSide(color: scheme.outlineVariant),
                  ),
                ),
                child: _ScrollableRegion(
                  padding: const EdgeInsets.all(AppSpacing.lg),
                  child: setup,
                ),
              ),
            ),
            Expanded(
              child: _ScrollableRegion(
                padding: const EdgeInsets.symmetric(
                  horizontal: AppSpacing.xl,
                  vertical: AppSpacing.lg,
                ),
                child: Center(
                  child: ConstrainedBox(
                    constraints: const BoxConstraints(maxWidth: 800),
                    child: content,
                  ),
                ),
              ),
            ),
          ],
        );
      },
    );
  }
}

class _ScrollableRegion extends StatelessWidget {
  const _ScrollableRegion({required this.padding, required this.child});

  final EdgeInsets padding;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    return Scrollbar(
      child: SingleChildScrollView(
        padding: padding,
        child: ConstrainedBox(
          constraints: BoxConstraints(
            minHeight: MediaQuery.sizeOf(context).height - 120,
          ),
          child: child,
        ),
      ),
    );
  }
}
