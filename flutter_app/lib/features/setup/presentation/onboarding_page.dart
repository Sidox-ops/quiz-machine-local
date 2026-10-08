import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../../core/design_system/atoms/app_brand_mark.dart';
import '../../../core/design_system/foundations/app_tokens.dart';
import '../../../core/runtime/local_backend_manager.dart';
import '../data/environment_repository.dart';
import '../domain/setup_models.dart';
import 'corpus_import_dialog.dart';

class OnboardingPage extends StatefulWidget {
  const OnboardingPage({
    required this.repository,
    required this.acceptanceStore,
    required this.onCompleted,
    super.key,
  });

  final EnvironmentRepository repository;
  final AcceptanceStore acceptanceStore;
  final VoidCallback onCompleted;

  @override
  State<OnboardingPage> createState() => _OnboardingPageState();
}

class _OnboardingPageState extends State<OnboardingPage> {
  late int _step;
  bool _termsAccepted = false;
  bool _busy = false;
  SystemDiagnostics? _diagnostics;
  String? _selectedModel;
  String? _status;
  String? _error;

  @override
  void initState() {
    super.initState();
    _step = widget.acceptanceStore.isAccepted() ? 1 : 0;
    if (_step == 1) _refresh();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Row(
          children: [
            AppBrandMark(),
            SizedBox(width: AppSpacing.sm),
            Text('Quiz Machine'),
          ],
        ),
      ),
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(AppSpacing.lg),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 720),
              child: AnimatedSwitcher(
                duration: AppMotion.resolve(context, AppMotion.standard),
                child: switch (_step) {
                  0 => _legalStep(),
                  1 => _systemStep(),
                  _ => _corpusStep(),
                },
              ),
            ),
          ),
        ),
      ),
    );
  }

  Widget _legalStep() {
    return Column(
      key: const ValueKey('legal'),
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text(
          'Before you begin',
          style: Theme.of(context).textTheme.headlineMedium,
        ),
        const SizedBox(height: AppSpacing.sm),
        Text(
          'Quiz Machine is an independent educational tool. It runs locally, '
          'collects no personal data and does not guarantee an exam result.',
          style: Theme.of(context).textTheme.bodyLarge,
        ),
        const SizedBox(height: AppSpacing.lg),
        _InfoBand(
          icon: Icons.lock_outline,
          title: 'Your content stays on this machine',
          body:
              'Imported corpora are stored locally and are never uploaded by the app.',
        ),
        const SizedBox(height: AppSpacing.sm),
        const _InfoBand(
          icon: Icons.language_outlined,
          title: 'Official course retrieval',
          body: 'Certification and domain searches are sent to the public '
              'Microsoft Learn service; no personal data is included.',
        ),
        const SizedBox(height: AppSpacing.sm),
        _InfoBand(
          icon: Icons.school_outlined,
          title: 'Independent practice tool',
          body: 'Not affiliated with, endorsed by or sponsored by Microsoft.',
        ),
        const SizedBox(height: AppSpacing.md),
        TextButton.icon(
          onPressed: _showTerms,
          icon: const Icon(Icons.description_outlined),
          label: const Text('Read open-source licence and privacy notice'),
        ),
        CheckboxListTile(
          contentPadding: EdgeInsets.zero,
          controlAffinity: ListTileControlAffinity.leading,
          value: _termsAccepted,
          onChanged: (value) => setState(() => _termsAccepted = value ?? false),
          title: const Text(
            'I have read the open-source licence and privacy notice.',
          ),
        ),
        const SizedBox(height: AppSpacing.md),
        Align(
          alignment: Alignment.centerRight,
          child: FilledButton.icon(
            onPressed: _termsAccepted
                ? () {
                    setState(() => _step = 1);
                    _refresh();
                  }
                : null,
            icon: const Icon(Icons.arrow_forward),
            label: const Text('Continue'),
          ),
        ),
      ],
    );
  }

  Widget _systemStep() {
    final diagnostics = _diagnostics;
    return Column(
      key: const ValueKey('system'),
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text('System check', style: Theme.of(context).textTheme.headlineMedium),
        const SizedBox(height: AppSpacing.sm),
        Text(
          'The quiz engine uses Ollama locally and retrieves official course '
          'content from Microsoft Learn when you generate a session.',
          style: Theme.of(context).textTheme.bodyLarge,
        ),
        const SizedBox(height: AppSpacing.md),
        const _InfoBand(
          icon: Icons.download_done_outlined,
          title: 'Installed models only',
          body: 'Quiz Machine detects models already available in Ollama. '
              'It never downloads or replaces a model during onboarding.',
        ),
        const SizedBox(height: AppSpacing.lg),
        if (diagnostics != null) ...[
          _CheckRow(
            label: '${diagnostics.platform} ${diagnostics.architecture}',
            detail: '${diagnostics.freeDiskGb.toStringAsFixed(1)} GB free',
            ok: diagnostics.diskReady,
            warning: !diagnostics.diskReady,
          ),
          _CheckRow(
            label: 'Ollama',
            detail: diagnostics.ollamaInstalled
                ? (diagnostics.ollamaReachable ? 'Running' : 'Installed')
                : 'Not installed',
            ok: diagnostics.ollamaInstalled && diagnostics.ollamaReachable,
          ),
          if (diagnostics.ollamaReachable &&
              diagnostics.compatibleModels.isNotEmpty) ...[
            const SizedBox(height: AppSpacing.sm),
            DropdownButtonFormField<String>(
              key: ValueKey(_selectedModel),
              initialValue: _selectedModel,
              isExpanded: true,
              decoration: const InputDecoration(
                labelText: 'Local generation model',
                prefixIcon: Icon(Icons.memory_outlined),
              ),
              items: diagnostics.compatibleModels
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
              onChanged: _busy || diagnostics.modelSelectionLocked
                  ? null
                  : (value) => setState(() => _selectedModel = value),
            ),
            const SizedBox(height: AppSpacing.xs),
            Text(
              _modelDescription(diagnostics),
              style: Theme.of(context).textTheme.bodySmall,
            ),
          ] else if (diagnostics.ollamaReachable)
            _CheckRow(
              label: 'Local generation model',
              detail: 'No compatible installed model detected',
              ok: false,
              warning: true,
            ),
          if (diagnostics.modelSelectionLocked)
            const Padding(
              padding: EdgeInsets.only(top: AppSpacing.xs),
              child: Text('Model selection is locked by AI103_LLM_MODEL.'),
            ),
          if (diagnostics.usesMicrosoftLearn)
            _CheckRow(
              label: 'Microsoft Learn',
              detail: diagnostics.knowledgeCheckCompleted &&
                      diagnostics.knowledgeReady
                  ? 'Connection checked'
                  : diagnostics.knowledgeReady
                      ? 'Cached courses found; connection check required'
                      : 'Connection check required',
              ok: diagnostics.knowledgeCheckCompleted &&
                  diagnostics.knowledgeReady,
            )
          else ...[
            _CheckRow(
              label: diagnostics.embeddingModel,
              detail: diagnostics.embeddingReady
                  ? 'Ready'
                  : 'Not installed in Ollama',
              ok: diagnostics.embeddingReady,
            ),
            _CheckRow(
              label: 'Study index',
              detail: diagnostics.indexReady
                  ? '${diagnostics.indexedChunks} chunks indexed'
                  : 'Build required',
              ok: diagnostics.indexReady,
            ),
          ],
        ] else if (_busy)
          const LinearProgressIndicator(),
        if (_status != null) ...[
          const SizedBox(height: AppSpacing.md),
          Text(_status!),
          const SizedBox(height: AppSpacing.xs),
          if (_busy) const LinearProgressIndicator(),
        ],
        if (_error != null) ...[
          const SizedBox(height: AppSpacing.md),
          Text(
            _error!,
            style: TextStyle(color: Theme.of(context).colorScheme.error),
          ),
        ],
        const SizedBox(height: AppSpacing.lg),
        Wrap(
          alignment: WrapAlignment.end,
          spacing: AppSpacing.sm,
          runSpacing: AppSpacing.sm,
          children: [
            if (diagnostics != null && !diagnostics.ollamaInstalled)
              OutlinedButton.icon(
                onPressed: _busy ? null : _openOllamaWebsite,
                icon: const Icon(Icons.open_in_new),
                label: const Text('Get Ollama'),
              ),
            if (diagnostics != null &&
                diagnostics.ollamaReachable &&
                diagnostics.compatibleModels.isEmpty)
              OutlinedButton.icon(
                onPressed: _busy ? null : _openOllamaLibrary,
                icon: const Icon(Icons.open_in_new),
                label: const Text('Browse Ollama models'),
              ),
            if (diagnostics != null &&
                diagnostics.ollamaInstalled &&
                !diagnostics.ollamaReachable)
              OutlinedButton.icon(
                onPressed: _busy ? null : _startOllama,
                icon: const Icon(Icons.play_circle_outline),
                label: const Text('Start Ollama'),
              ),
            OutlinedButton.icon(
              onPressed: _busy ? null : _refresh,
              icon: const Icon(Icons.refresh),
              label: const Text('Check again'),
            ),
            if (diagnostics != null &&
                !diagnostics.modelSelectionLocked &&
                _selectedModel != null &&
                diagnostics.llmModel != _selectedModel)
              FilledButton.icon(
                onPressed: _busy ? null : () => _selectModel(_selectedModel!),
                icon: const Icon(Icons.check_circle_outline),
                label: const Text('Use selected model'),
              )
            else if (diagnostics != null &&
                diagnostics.llmReady &&
                !diagnostics.ready)
              FilledButton.icon(
                onPressed: _busy ? null : _prepare,
                icon: const Icon(Icons.verified_outlined),
                label: const Text('Verify services'),
              ),
            if (diagnostics?.ready == true)
              FilledButton.icon(
                onPressed: () => setState(() => _step = 2),
                icon: const Icon(Icons.arrow_forward),
                label: const Text('Continue'),
              ),
          ],
        ),
      ],
    );
  }

  Widget _corpusStep() {
    return Column(
      key: const ValueKey('corpus'),
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text(
          'Choose your material',
          style: Theme.of(context).textTheme.headlineMedium,
        ),
        const SizedBox(height: AppSpacing.sm),
        Text(
          'Choose a Microsoft certification in the next screen. Official Learn '
          'courses will ground the QCM while inference remains on this computer.',
          style: Theme.of(context).textTheme.bodyLarge,
        ),
        const SizedBox(height: AppSpacing.lg),
        _InfoBand(
          icon: Icons.auto_awesome_outlined,
          title: 'Microsoft Learn + Ollama',
          body: 'Course retrieval is online. Questions, answers, and progress '
              'remain stored locally.',
        ),
        const SizedBox(height: AppSpacing.lg),
        Wrap(
          alignment: WrapAlignment.end,
          spacing: AppSpacing.sm,
          runSpacing: AppSpacing.sm,
          children: [
            OutlinedButton.icon(
              onPressed: _busy ? null : _importCorpus,
              icon: const Icon(Icons.folder_open_outlined),
              label: const Text('Import JSON'),
            ),
            FilledButton.icon(
              onPressed: _finish,
              icon: const Icon(Icons.play_arrow),
              label: const Text('Start practicing'),
            ),
          ],
        ),
      ],
    );
  }

  Future<void> _refresh() async {
    setState(() {
      _busy = true;
      _error = null;
      _status = 'Checking the local environment...';
    });
    try {
      final result = await widget.repository.diagnostics();
      if (!mounted) return;
      _applyDiagnostics(result, status: null);
    } catch (exception) {
      if (mounted) setState(() => _error = exception.toString());
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _prepare() async {
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final result = await widget.repository.prepare((status) {
        if (mounted) setState(() => _status = status.message);
      });
      if (!mounted) return;
      _applyDiagnostics(result, status: 'Ready.');
    } catch (exception) {
      if (mounted) setState(() => _error = exception.toString());
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _selectModel(String model) async {
    setState(() {
      _busy = true;
      _error = null;
      _status = 'Testing structured output with $model...';
    });
    try {
      final result = await widget.repository.selectModel(model);
      if (!mounted) return;
      _applyDiagnostics(result,
          status: '$model passed the local test and was selected.');
    } catch (exception) {
      if (mounted) setState(() => _error = exception.toString());
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  void _applyDiagnostics(SystemDiagnostics result, {required String? status}) {
    final compatibleNames =
        result.compatibleModels.map((model) => model.name).toSet();
    final preferred = compatibleNames.contains(result.llmModel)
        ? result.llmModel
        : compatibleNames.contains(_selectedModel)
            ? _selectedModel
            : compatibleNames.contains(result.recommendedLlmModel)
                ? result.recommendedLlmModel
                : result.compatibleModels.isEmpty
                    ? null
                    : result.compatibleModels.first.name;
    setState(() {
      _diagnostics = result;
      _selectedModel = preferred;
      _status = status;
    });
  }

  String _modelDescription(SystemDiagnostics diagnostics) {
    final matches = diagnostics.compatibleModels
        .where((model) => model.name == _selectedModel)
        .toList(growable: false);
    final selected = matches.isEmpty ? null : matches.first;
    if (selected == null) return 'Choose an installed local chat model.';
    final recommendation = diagnostics.modelRecommendationReason.isEmpty
        ? 'Recommended for this machine.'
        : diagnostics.modelRecommendationReason;
    final prefix = selected.recommended
        ? '$recommendation '
        : 'Installed compatible model.';
    final license =
        selected.license.isEmpty ? '' : ' Licence: ${selected.license}.';
    final warning = selected.fitsMemory == false
        ? ' This model may exceed the recommended memory budget.'
        : '';
    return '$prefix ${selected.summary}.$license$warning';
  }

  Future<void> _importCorpus() async {
    final summary = await CorpusImportDialog.show(context, widget.repository);
    if (!mounted || summary == null) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(
          '${summary.title}: ${summary.chunkCount} chunks imported.',
        ),
      ),
    );
    await _refresh();
  }

  void _finish() {
    widget.acceptanceStore.accept();
    widget.onCompleted();
  }

  Future<void> _openOllamaWebsite() async {
    const url = 'https://ollama.com/download';
    if (Platform.isMacOS) {
      await Process.run('open', [url]);
    } else if (Platform.isWindows) {
      await Process.run('cmd', ['/c', 'start', '', url]);
    }
  }

  Future<void> _openOllamaLibrary() =>
      _openExternalUrl('https://ollama.com/library');

  Future<void> _openExternalUrl(String url) async {
    if (Platform.isMacOS) {
      await Process.run('open', [url]);
    } else if (Platform.isWindows) {
      await Process.run('cmd', ['/c', 'start', '', url]);
    }
  }

  Future<void> _startOllama() async {
    setState(() {
      _busy = true;
      _error = null;
      _status = 'Starting Ollama...';
    });
    try {
      if (Platform.isMacOS) {
        await Process.run('open', ['-a', 'Ollama']);
      } else if (Platform.isWindows) {
        await Process.start(
            'ollama',
            const [
              'serve',
            ],
            mode: ProcessStartMode.detached);
      }
      await Future<void>.delayed(const Duration(seconds: 3));
      await _refresh();
    } catch (exception) {
      if (mounted) setState(() => _error = exception.toString());
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  void _showTerms() {
    showDialog<void>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Open-source licence and privacy'),
        content: SizedBox(
          width: 560,
          child: SingleChildScrollView(
            child: FutureBuilder<String>(
              future: rootBundle.loadString('assets/legal/terms.txt'),
              builder: (context, snapshot) {
                if (snapshot.hasError) {
                  return const Text('The legal terms could not be loaded.');
                }
                return SelectableText(snapshot.data ?? 'Loading...');
              },
            ),
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(),
            child: const Text('Close'),
          ),
        ],
      ),
    );
  }
}

class _InfoBand extends StatelessWidget {
  const _InfoBand({
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
        border: Border.all(color: scheme.outlineVariant),
        borderRadius: AppRadii.panel,
      ),
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.md),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Icon(icon, color: scheme.primary),
            const SizedBox(width: AppSpacing.md),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(title, style: Theme.of(context).textTheme.titleMedium),
                  const SizedBox(height: AppSpacing.xxs),
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

class _CheckRow extends StatelessWidget {
  const _CheckRow({
    required this.label,
    required this.detail,
    required this.ok,
    this.warning = false,
  });

  final String label;
  final String detail;
  final bool ok;
  final bool warning;

  @override
  Widget build(BuildContext context) {
    final color = ok
        ? context.semanticColors.success
        : warning
            ? context.semanticColors.attention
            : Theme.of(context).colorScheme.error;
    final status = ok
        ? 'ready'
        : warning
            ? 'warning'
            : 'not ready';
    return Semantics(
      container: true,
      label: '$label, $detail, $status',
      excludeSemantics: true,
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: AppSpacing.sm),
        child: Row(
          children: [
            Icon(
              ok
                  ? Icons.check_circle
                  : warning
                      ? Icons.warning
                      : Icons.cancel,
              color: color,
            ),
            const SizedBox(width: AppSpacing.sm),
            Expanded(
              child:
                  Text(label, style: Theme.of(context).textTheme.titleMedium),
            ),
            const SizedBox(width: AppSpacing.sm),
            Flexible(child: Text(detail, textAlign: TextAlign.end)),
          ],
        ),
      ),
    );
  }
}
