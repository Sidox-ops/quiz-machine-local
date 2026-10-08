import 'package:flutter/material.dart';

import '../../../core/design_system/foundations/app_tokens.dart';
import '../data/environment_repository.dart';
import '../domain/setup_models.dart';

class ModelSelectionDialog extends StatefulWidget {
  const ModelSelectionDialog({required this.repository, super.key});

  final EnvironmentRepository repository;

  static Future<String?> show(
    BuildContext context,
    EnvironmentRepository repository,
  ) {
    return showDialog<String>(
      context: context,
      builder: (context) => ModelSelectionDialog(repository: repository),
    );
  }

  @override
  State<ModelSelectionDialog> createState() => _ModelSelectionDialogState();
}

class _ModelSelectionDialogState extends State<ModelSelectionDialog> {
  SystemDiagnostics? _diagnostics;
  String? _selectedModel;
  String? _error;
  bool _busy = true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  Widget build(BuildContext context) {
    final diagnostics = _diagnostics;
    final compatible =
        diagnostics?.compatibleModels ?? const <LocalModelInfo>[];
    final selected =
        compatible.where((model) => model.name == _selectedModel).firstOrNull;
    final recommendationReason =
        diagnostics?.modelRecommendationReason.isNotEmpty == true
            ? diagnostics!.modelRecommendationReason
            : 'Recommended for this machine.';

    return AlertDialog(
      title: const Text('Local Ollama model'),
      content: SizedBox(
        width: 560,
        child: _busy && diagnostics == null
            ? const Padding(
                padding: EdgeInsets.all(AppSpacing.xl),
                child: Center(child: CircularProgressIndicator()),
              )
            : SingleChildScrollView(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    const Text(
                      'Choose among models already installed in Ollama. Quiz '
                      'Machine never downloads or replaces a model here.',
                    ),
                    const SizedBox(height: AppSpacing.md),
                    if (diagnostics?.modelSelectionLocked == true)
                      const _Notice(
                        icon: Icons.lock_outline,
                        text: 'Selection is locked by AI103_LLM_MODEL. Change '
                            'that environment variable and restart the app to '
                            'use another model.',
                      )
                    else if (compatible.isEmpty)
                      const _Notice(
                        icon: Icons.warning_amber_outlined,
                        text: 'No compatible local generation model was found. '
                            'Install one in Ollama, then check again.',
                      )
                    else ...[
                      DropdownButtonFormField<String>(
                        key: ValueKey(_selectedModel),
                        initialValue: _selectedModel,
                        isExpanded: true,
                        decoration: const InputDecoration(
                          labelText: 'Generation model',
                          prefixIcon: Icon(Icons.memory_outlined),
                        ),
                        items: compatible
                            .map(
                              (model) => DropdownMenuItem<String>(
                                value: model.name,
                                child: Text(
                                  model.recommended
                                      ? '${model.name} (recommended)'
                                      : model.name,
                                  overflow: TextOverflow.ellipsis,
                                ),
                              ),
                            )
                            .toList(growable: false),
                        onChanged: _busy
                            ? null
                            : (value) => setState(() => _selectedModel = value),
                      ),
                      const SizedBox(height: AppSpacing.sm),
                      if (selected != null)
                        Text(
                          '${selected.summary}\n${selected.recommended ? '$recommendationReason ' : ''}'
                          '${selected.license.isEmpty ? '' : 'Licence: ${selected.license}. '}'
                          '${selected.fitsMemory == false ? 'This model may exceed the recommended memory budget. ' : ''}'
                          'The change applies to future question generation; '
                          'prepared sessions and validated questions are kept.',
                          style: Theme.of(context).textTheme.bodySmall,
                        ),
                    ],
                    if (_error != null) ...[
                      const SizedBox(height: AppSpacing.md),
                      Text(
                        _error!,
                        style: TextStyle(
                          color: Theme.of(context).colorScheme.error,
                        ),
                      ),
                    ],
                    if (_busy && diagnostics != null) ...[
                      const SizedBox(height: AppSpacing.md),
                      const LinearProgressIndicator(),
                    ],
                  ],
                ),
              ),
      ),
      actions: [
        TextButton(
          onPressed: _busy ? null : _load,
          child: const Text('Check again'),
        ),
        TextButton(
          onPressed: () => Navigator.of(context).pop(),
          child: const Text('Close'),
        ),
        if (diagnostics != null && !diagnostics.modelSelectionLocked)
          FilledButton(
            onPressed: _busy ||
                    _selectedModel == null ||
                    _selectedModel == diagnostics.llmModel
                ? null
                : _save,
            child: const Text('Test and use model'),
          ),
      ],
    );
  }

  Future<void> _load() async {
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final result = await widget.repository.diagnostics();
      if (!mounted) return;
      _applyDiagnostics(result);
    } catch (exception) {
      if (mounted) setState(() => _error = exception.toString());
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _save() async {
    final model = _selectedModel;
    if (model == null) return;
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await widget.repository.selectModel(model);
      if (mounted) Navigator.of(context).pop(model);
    } catch (exception) {
      if (mounted) setState(() => _error = exception.toString());
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  void _applyDiagnostics(SystemDiagnostics diagnostics) {
    final compatibleNames =
        diagnostics.compatibleModels.map((model) => model.name).toSet();
    setState(() {
      _diagnostics = diagnostics;
      _selectedModel = compatibleNames.contains(diagnostics.llmModel)
          ? diagnostics.llmModel
          : compatibleNames.contains(_selectedModel)
              ? _selectedModel
              : compatibleNames.contains(diagnostics.recommendedLlmModel)
                  ? diagnostics.recommendedLlmModel
                  : diagnostics.compatibleModels.firstOrNull?.name;
    });
  }
}

class _Notice extends StatelessWidget {
  const _Notice({required this.icon, required this.text});

  final IconData icon;
  final String text;

  @override
  Widget build(BuildContext context) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Icon(icon, color: Theme.of(context).colorScheme.primary),
        const SizedBox(width: AppSpacing.sm),
        Expanded(child: Text(text)),
      ],
    );
  }
}
