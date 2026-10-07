import 'package:flutter/material.dart';

import '../../../../core/design_system/foundations/app_tokens.dart';
import '../../../../core/design_system/foundations/app_typography.dart';
import '../../domain/quiz_models.dart';
import '../view_models/quiz_view_model.dart';

class ProgressDashboardPage extends StatelessWidget {
  const ProgressDashboardPage({required this.viewModel, super.key});

  final QuizViewModel viewModel;

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: viewModel,
      builder: (context, _) {
        final progress = viewModel.progress;
        return Scaffold(
          appBar: AppBar(
            title: const Text('Learning dashboard'),
            actions: [
              TextButton.icon(
                onPressed: () => _showResetFlow(context),
                icon: const Icon(Icons.restart_alt),
                label: const Text('Reset data'),
              ),
              const SizedBox(width: AppSpacing.sm),
            ],
          ),
          body: SafeArea(
            child: SingleChildScrollView(
              padding: const EdgeInsets.all(AppSpacing.lg),
              child: Center(
                child: ConstrainedBox(
                  constraints: const BoxConstraints(maxWidth: 1180),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      _PageLead(
                        certificationCode: viewModel.selectedCertificationCode,
                      ),
                      const SizedBox(height: AppSpacing.xl),
                      _KpiGrid(progress: progress),
                      const SizedBox(height: AppSpacing.xl),
                      if (progress.asked == 0)
                        const _EmptyProgress()
                      else ...[
                        _LearningGrid(progress: progress),
                        if (progress.confusions.isNotEmpty) ...[
                          const SizedBox(height: AppSpacing.xl),
                          _ConfusionPanel(confusions: progress.confusions),
                        ],
                      ],
                    ],
                  ),
                ),
              ),
            ),
          ),
        );
      },
    );
  }

  Future<void> _showResetFlow(BuildContext context) async {
    final scope = await showDialog<ProgressResetScope>(
      context: context,
      builder: (context) => _ResetProgressDialog(
        certificationCode: viewModel.selectedCertificationCode,
      ),
    );
    if (scope == null || !context.mounted) return;
    try {
      await viewModel.resetProgress(scope);
      if (!context.mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Learning data reset completed.')),
      );
    } catch (_) {
      if (!context.mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('The reset could not be completed.')),
      );
    }
  }
}

class _PageLead extends StatelessWidget {
  const _PageLead({required this.certificationCode});

  final String certificationCode;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          'LEARNING SIGNALS · $certificationCode',
          style: theme.textTheme.labelMedium?.copyWith(
            color: theme.colorScheme.primary,
          ),
        ),
        const SizedBox(height: AppSpacing.xs),
        Text('Your preparation, made useful',
            style: theme.textTheme.headlineMedium),
        const SizedBox(height: AppSpacing.xs),
        Text(
          'Read the trend, spot weak objectives, then return to a targeted batch. '
          'Statistics are isolated to the active certification.',
          style: theme.textTheme.bodyLarge?.copyWith(
            color: theme.colorScheme.onSurfaceVariant,
          ),
        ),
      ],
    );
  }
}

class _KpiGrid extends StatelessWidget {
  const _KpiGrid({required this.progress});

  final QuizProgress progress;

  @override
  Widget build(BuildContext context) {
    final metrics = [
      _Kpi('Questions answered', '${progress.asked}',
          '${progress.correct} correct · ${progress.incorrect} to review'),
      _Kpi('Overall accuracy', '${progress.percent}%',
          progress.asked == 0 ? 'No signal yet' : 'Across this certification'),
      _Kpi('Recent accuracy', '${progress.recentPercent}%',
          '${progress.recentAttemptCount} recent answer(s) retained'),
      _Kpi(
        'Average response',
        progress.averageSeconds == null
            ? '—'
            : '${progress.averageSeconds!.round()}s',
        'Timed answers only',
      ),
    ];
    return LayoutBuilder(
      builder: (context, constraints) {
        final columns = constraints.maxWidth >= 920
            ? 4
            : constraints.maxWidth >= 560
                ? 2
                : 1;
        final width =
            (constraints.maxWidth - AppSpacing.sm * (columns - 1)) / columns;
        return Wrap(
          spacing: AppSpacing.sm,
          runSpacing: AppSpacing.sm,
          children: metrics
              .map((metric) => SizedBox(width: width, child: _KpiCard(metric)))
              .toList(growable: false),
        );
      },
    );
  }
}

class _Kpi {
  const _Kpi(this.label, this.value, this.detail);

  final String label;
  final String value;
  final String detail;
}

class _KpiCard extends StatelessWidget {
  const _KpiCard(this.metric);

  final _Kpi metric;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Container(
      height: 150,
      padding: const EdgeInsets.all(AppSpacing.md),
      decoration: BoxDecoration(
        color: theme.colorScheme.surfaceContainerLow,
        border: Border.all(color: theme.colorScheme.outlineVariant),
        borderRadius: AppRadii.panel,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(metric.label, style: theme.textTheme.labelLarge),
          const Spacer(),
          Text(
            metric.value,
            style: AppTypography.data(
              fontSize: 36,
              color: theme.colorScheme.primary,
            ),
          ),
          const SizedBox(height: AppSpacing.xs),
          Text(
            metric.detail,
            maxLines: 2,
            style: theme.textTheme.bodySmall?.copyWith(
              color: theme.colorScheme.onSurfaceVariant,
            ),
          ),
        ],
      ),
    );
  }
}

class _LearningGrid extends StatelessWidget {
  const _LearningGrid({required this.progress});

  final QuizProgress progress;

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final domains = _BreakdownPanel(
          title: 'Domain coverage',
          description: 'Accuracy by exam domain.',
          metrics: progress.domains,
          emptyMessage: 'Answer more questions to reveal domain coverage.',
        );
        final objectives = _BreakdownPanel(
          title: 'Priority objectives',
          description: 'Weakest measured objectives appear first.',
          metrics: progress.objectives.take(6).toList(growable: false),
          emptyMessage: 'No objective-level signal is available yet.',
        );
        if (constraints.maxWidth < 820) {
          return Column(
            children: [
              domains,
              const SizedBox(height: AppSpacing.md),
              objectives
            ],
          );
        }
        return Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Expanded(child: domains),
            const SizedBox(width: AppSpacing.md),
            Expanded(child: objectives),
          ],
        );
      },
    );
  }
}

class _BreakdownPanel extends StatelessWidget {
  const _BreakdownPanel({
    required this.title,
    required this.description,
    required this.metrics,
    required this.emptyMessage,
  });

  final String title;
  final String description;
  final List<ProgressMetric> metrics;
  final String emptyMessage;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Container(
      padding: const EdgeInsets.all(AppSpacing.lg),
      decoration: BoxDecoration(
        color: theme.colorScheme.surfaceContainerLowest,
        border: Border.all(color: theme.colorScheme.outlineVariant),
        borderRadius: AppRadii.panel,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(title, style: theme.textTheme.titleLarge),
          const SizedBox(height: AppSpacing.xxs),
          Text(
            description,
            style: theme.textTheme.bodyMedium?.copyWith(
              color: theme.colorScheme.onSurfaceVariant,
            ),
          ),
          const SizedBox(height: AppSpacing.lg),
          if (metrics.isEmpty)
            Text(emptyMessage)
          else
            for (final metric in metrics) ...[
              _MetricRow(metric: metric),
              if (metric != metrics.last) const SizedBox(height: AppSpacing.md),
            ],
        ],
      ),
    );
  }
}

class _MetricRow extends StatelessWidget {
  const _MetricRow({required this.metric});

  final ProgressMetric metric;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Expanded(
              child: Text(
                metric.label,
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
                style: theme.textTheme.labelLarge,
              ),
            ),
            const SizedBox(width: AppSpacing.sm),
            Text('${metric.percent}%', style: theme.textTheme.titleMedium),
          ],
        ),
        const SizedBox(height: AppSpacing.xs),
        LinearProgressIndicator(value: metric.accuracy.clamp(0, 1)),
        const SizedBox(height: AppSpacing.xxs),
        Text(
          '${metric.correct}/${metric.asked} correct',
          style: theme.textTheme.bodySmall?.copyWith(
            color: theme.colorScheme.onSurfaceVariant,
          ),
        ),
      ],
    );
  }
}

class _ConfusionPanel extends StatelessWidget {
  const _ConfusionPanel({required this.confusions});

  final List<ProgressConfusion> confusions;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Container(
      padding: const EdgeInsets.all(AppSpacing.lg),
      decoration: BoxDecoration(
        color: theme.colorScheme.surfaceContainerLowest,
        border: Border.all(color: theme.colorScheme.outlineVariant),
        borderRadius: AppRadii.panel,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text('Recurring confusions', style: theme.textTheme.titleLarge),
          const SizedBox(height: AppSpacing.xxs),
          Text(
            'Mistakes worth revisiting before the next mixed batch.',
            style: theme.textTheme.bodyMedium?.copyWith(
              color: theme.colorScheme.onSurfaceVariant,
            ),
          ),
          const SizedBox(height: AppSpacing.md),
          for (final confusion in confusions.take(4))
            ListTile(
              contentPadding: EdgeInsets.zero,
              leading: CircleAvatar(
                child: Text('${confusion.count}'),
              ),
              title: Text(confusion.learningObjective),
              subtitle: Text(
                'Confused “${confusion.selectedOptionText}” with '
                '“${confusion.correctOptionText}”.',
              ),
            ),
        ],
      ),
    );
  }
}

class _EmptyProgress extends StatelessWidget {
  const _EmptyProgress();

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Container(
      padding: const EdgeInsets.all(AppSpacing.xl),
      decoration: BoxDecoration(
        color: theme.colorScheme.surfaceContainerLow,
        borderRadius: AppRadii.panel,
      ),
      child: const Column(
        children: [
          Icon(Icons.insights_outlined, size: 40),
          SizedBox(height: AppSpacing.sm),
          Text('Your dashboard will learn with you.'),
          SizedBox(height: AppSpacing.xs),
          Text('Complete a first question batch to reveal useful signals.'),
        ],
      ),
    );
  }
}

class _ResetProgressDialog extends StatefulWidget {
  const _ResetProgressDialog({required this.certificationCode});

  final String certificationCode;

  @override
  State<_ResetProgressDialog> createState() => _ResetProgressDialogState();
}

class _ResetProgressDialogState extends State<_ResetProgressDialog> {
  ProgressResetScope _scope = ProgressResetScope.recentActivity;
  final _confirmationController = TextEditingController();

  @override
  void dispose() {
    _confirmationController.dispose();
    super.dispose();
  }

  bool get _requiresPhrase =>
      _scope == ProgressResetScope.certification ||
      _scope == ProgressResetScope.all;

  String get _phrase =>
      _scope == ProgressResetScope.all ? 'RESET ALL' : widget.certificationCode;

  bool get _canConfirm =>
      !_requiresPhrase || _confirmationController.text.trim() == _phrase;

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('Reset learning data'),
      content: SizedBox(
        width: 540,
        child: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              _option(
                ProgressResetScope.recentActivity,
                'Recent trend only',
                'Clears the 20-answer trend and timing history. Lifetime totals stay.',
              ),
              _option(
                ProgressResetScope.adaptiveProfile,
                'Adaptive profile',
                'Clears weak domains, objectives and confusions for ${widget.certificationCode}.',
              ),
              _option(
                ProgressResetScope.certification,
                '${widget.certificationCode} statistics',
                'Deletes all learning data for the active certification.',
              ),
              _option(
                ProgressResetScope.all,
                'Everything',
                'Deletes progress for every certification. Corpora and question banks stay.',
              ),
              if (_requiresPhrase) ...[
                const SizedBox(height: AppSpacing.md),
                TextField(
                  controller: _confirmationController,
                  onChanged: (_) => setState(() {}),
                  decoration: InputDecoration(
                    labelText: 'Type $_phrase to confirm',
                  ),
                ),
              ],
            ],
          ),
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context),
          child: const Text('Cancel'),
        ),
        FilledButton(
          onPressed: _canConfirm ? () => Navigator.pop(context, _scope) : null,
          child: const Text('Reset selected data'),
        ),
      ],
    );
  }

  Widget _option(ProgressResetScope value, String title, String subtitle) {
    final selected = value == _scope;
    final colors = Theme.of(context).colorScheme;
    return Padding(
      padding: const EdgeInsets.only(bottom: AppSpacing.xs),
      child: ListTile(
        selected: selected,
        selectedTileColor: colors.primaryContainer.withValues(alpha: 0.45),
        shape: const RoundedRectangleBorder(borderRadius: AppRadii.control),
        leading: Icon(
          selected ? Icons.radio_button_checked : Icons.radio_button_off,
          color: selected ? colors.primary : colors.onSurfaceVariant,
        ),
        contentPadding: const EdgeInsets.symmetric(horizontal: AppSpacing.sm),
        title: Text(title),
        subtitle: Text(subtitle),
        onTap: () {
          setState(() {
            _scope = value;
            _confirmationController.clear();
          });
        },
      ),
    );
  }
}
