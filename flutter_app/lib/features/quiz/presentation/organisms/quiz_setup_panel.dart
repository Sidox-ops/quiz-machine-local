import 'package:flutter/material.dart';

import '../../../../core/design_system/foundations/app_tokens.dart';
import '../../../../core/design_system/molecules/labeled_control.dart';
import '../../../../core/design_system/molecules/score_summary.dart';
import '../../domain/quiz_models.dart';
import '../view_models/quiz_view_model.dart';

class QuizSetupPanel extends StatelessWidget {
  const QuizSetupPanel({
    required this.viewModel,
    this.onGenerate,
    super.key,
  });

  final QuizViewModel viewModel;
  final VoidCallback? onGenerate;

  @override
  Widget build(BuildContext context) {
    final disabled = viewModel.isBusy;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text('Practice session', style: Theme.of(context).textTheme.titleLarge),
        const SizedBox(height: AppSpacing.lg),
        ScoreSummary(progress: viewModel.progress),
        const SizedBox(height: AppSpacing.xl),
        if (viewModel.catalog.certifications.isNotEmpty) ...[
          LabeledControl(
            label: 'Certification',
            child: _SelectField<String>(
              value: viewModel.selectedCertificationCode,
              values: viewModel.catalog.certifications
                  .map((item) => item.code)
                  .toList(growable: false),
              labelFor: (value) => viewModel.catalog.certifications
                  .firstWhere((item) => item.code == value)
                  .label,
              onChanged: disabled ? null : viewModel.setCertification,
            ),
          ),
          const SizedBox(height: AppSpacing.lg),
        ],
        if (viewModel.catalog.knowledgeProvider == 'microsoft_learn_mcp' ||
            viewModel.catalog.knowledgeProvider == 'hybrid') ...[
          Card(
            margin: EdgeInsets.zero,
            child: ListTile(
              leading: Icon(
                viewModel.catalog.knowledgeProvider == 'hybrid'
                    ? Icons.hub_outlined
                    : Icons.school_outlined,
              ),
              title: Text(
                viewModel.catalog.knowledgeProvider == 'hybrid'
                    ? 'Compact corpus + imported Markdown'
                    : 'Compact Microsoft Learn corpus',
              ),
              subtitle: Text(
                viewModel.catalog.knowledgeProvider == 'hybrid'
                    ? 'Imported material is included when it maps to an objective; question generation stays local.'
                    : viewModel.catalog.coverage.complete
                        ? 'Prepared locally; Microsoft Learn is not queried while questions are generated.'
                        : 'Prepared automatically from Microsoft Learn before the first session.',
              ),
            ),
          ),
          const SizedBox(height: AppSpacing.lg),
        ],
        LabeledControl(
          label: 'Coverage',
          child: SegmentedButton<QuizMode>(
            segments: [
              const ButtonSegment(
                value: QuizMode.shuffle,
                label: Text('Mixed'),
              ),
              const ButtonSegment(
                value: QuizMode.domain,
                label: Text('Domain'),
              ),
              if (viewModel.catalog.chapters.isNotEmpty)
                const ButtonSegment(
                  value: QuizMode.chapter,
                  label: Text('Chapter'),
                ),
            ],
            selected: {viewModel.mode},
            showSelectedIcon: false,
            onSelectionChanged: disabled
                ? null
                : (selection) => viewModel.setMode(selection.first),
          ),
        ),
        if (viewModel.catalog.sources.isNotEmpty) ...[
          const SizedBox(height: AppSpacing.md),
          _CorpusCoveragePanel(catalog: viewModel.catalog),
        ],
        if (viewModel.mode == QuizMode.domain) ...[
          const SizedBox(height: AppSpacing.lg),
          LabeledControl(
            label: 'Domain',
            child: _SelectField<String>(
              value: viewModel.selectedDomain,
              values: viewModel.catalog.domains,
              labelFor: (value) => value,
              onChanged: disabled ? null : viewModel.setDomain,
            ),
          ),
        ],
        if (viewModel.mode == QuizMode.chapter) ...[
          const SizedBox(height: AppSpacing.lg),
          LabeledControl(
            label: 'Chapter',
            child: _SelectField<String>(
              value: viewModel.selectedChapterId,
              values:
                  viewModel.catalog.chapters.map((item) => item.id).toList(),
              labelFor: (value) => viewModel.catalog.chapters
                  .firstWhere((item) => item.id == value)
                  .label,
              onChanged: disabled ? null : viewModel.setChapter,
            ),
          ),
        ],
        const SizedBox(height: AppSpacing.lg),
        LabeledControl(
          label: 'Question format',
          child: SegmentedButton<QuizQuestionFormat>(
            segments: const [
              ButtonSegment(
                value: QuizQuestionFormat.mixed,
                label: Text('Mixed'),
              ),
              ButtonSegment(
                value: QuizQuestionFormat.standard,
                label: Text('QCM'),
              ),
              ButtonSegment(
                value: QuizQuestionFormat.caseStudy,
                label: Text('Cases'),
              ),
            ],
            selected: {viewModel.questionFormat},
            showSelectedIcon: false,
            onSelectionChanged: disabled
                ? null
                : (selection) => viewModel.setQuestionFormat(selection.first),
          ),
        ),
        const SizedBox(height: AppSpacing.lg),
        LabeledControl(
          label: 'Difficulty',
          child: _SelectField<QuizDifficulty>(
            value: viewModel.difficulty,
            values: QuizDifficulty.values,
            labelFor: (value) => value.label,
            onChanged: disabled
                ? null
                : (value) {
                    if (value != null) viewModel.setDifficulty(value);
                  },
          ),
        ),
        const SizedBox(height: AppSpacing.lg),
        LabeledControl(
          label: 'Questions',
          trailing: Text(
            viewModel.questionCount.toString(),
            style: Theme.of(context).textTheme.titleMedium,
          ),
          child: Slider(
            value: viewModel.questionCount.toDouble(),
            min: 1,
            max: 50,
            divisions: 49,
            label: viewModel.questionCount.toString(),
            onChanged: disabled
                ? null
                : (value) => viewModel.setQuestionCount(value.round()),
          ),
        ),
        const SizedBox(height: AppSpacing.lg),
        FilledButton.icon(
          onPressed: disabled
              ? null
              : () {
                  onGenerate?.call();
                  viewModel.generateQuiz();
                },
          icon: const Icon(Icons.play_arrow),
          label: const Text('Start session'),
        ),
      ],
    );
  }
}

class _CorpusCoveragePanel extends StatelessWidget {
  const _CorpusCoveragePanel({required this.catalog});

  final QuizCatalog catalog;

  @override
  Widget build(BuildContext context) {
    final coverage = catalog.coverage;
    final colors = Theme.of(context).colorScheme;
    final statusColor = coverage.complete ? colors.primary : colors.error;
    return Card(
      margin: EdgeInsets.zero,
      child: ExpansionTile(
        leading: Icon(
          coverage.complete
              ? Icons.verified_outlined
              : Icons.warning_amber_rounded,
          color: statusColor,
        ),
        title: Text(
          '${coverage.indexedSources}/${coverage.expectedSources} '
          'corpora indexed',
        ),
        subtitle: Text(
          '${coverage.indexedChunks}/${coverage.expectedChunks} chunks • '
          '${coverage.complete ? 'Ready locally' : 'Prepared at session start'}',
        ),
        children: catalog.sources
            .map(
              (source) => ListTile(
                dense: true,
                leading: Icon(
                  source.isExcluded
                      ? Icons.block_outlined
                      : source.isCurrent
                          ? Icons.check_circle_outline
                          : Icons.error_outline,
                  color: source.isExcluded
                      ? colors.onSurfaceVariant
                      : source.isCurrent
                          ? colors.primary
                          : colors.error,
                ),
                title: Text(source.title),
                subtitle: Text(
                  source.isExcluded
                      ? 'Excluded • ${source.reason}'
                      : '${source.indexedChunks}/${source.expectedChunks} chunks'
                          '${source.chapterCount == 0 ? '' : ' • ${source.chapterCount} chapters'}',
                ),
              ),
            )
            .toList(growable: false),
      ),
    );
  }
}

class _SelectField<T> extends StatelessWidget {
  const _SelectField({
    required this.value,
    required this.values,
    required this.labelFor,
    required this.onChanged,
  });

  final T? value;
  final List<T> values;
  final String Function(T value) labelFor;
  final ValueChanged<T?>? onChanged;

  @override
  Widget build(BuildContext context) {
    return InputDecorator(
      decoration: const InputDecoration(),
      child: DropdownButtonHideUnderline(
        child: DropdownButton<T>(
          value: values.contains(value) ? value : null,
          isExpanded: true,
          isDense: true,
          borderRadius: AppRadii.control,
          items: values
              .map(
                (item) => DropdownMenuItem<T>(
                  value: item,
                  child: Text(labelFor(item), overflow: TextOverflow.ellipsis),
                ),
              )
              .toList(growable: false),
          onChanged: onChanged,
        ),
      ),
    );
  }
}
