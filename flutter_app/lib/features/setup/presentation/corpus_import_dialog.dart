import 'package:desktop_drop/desktop_drop.dart';
import 'package:file_selector/file_selector.dart';
import 'package:flutter/material.dart';

import '../../../core/design_system/foundations/app_tokens.dart';
import '../../quiz/data/quiz_api_service.dart';
import '../data/environment_repository.dart';
import '../domain/setup_models.dart';

const _markdownExample = '''---
schema: quiz-machine-corpus/v1
document_id: ai103-foundry-evaluation
certification_code: AI-103
domain: Plan and manage an Azure AI solution
title: Foundry evaluation notes
language: en
source_url: https://learn.microsoft.com/azure/ai-foundry/
learning_objective: Evaluate and select models for an AI solution
---

# Foundry evaluation notes

## Evaluation criteria

Use a representative test dataset to compare quality, safety, latency and cost.

## Operational checks

Record model versions and evaluation settings so results remain reproducible.
''';

class CorpusImportDialog extends StatefulWidget {
  const CorpusImportDialog({required this.repository, super.key});

  final EnvironmentRepository repository;

  static Future<CorpusSummary?> show(
    BuildContext context,
    EnvironmentRepository repository,
  ) {
    return showDialog<CorpusSummary>(
      context: context,
      builder: (_) => CorpusImportDialog(repository: repository),
    );
  }

  @override
  State<CorpusImportDialog> createState() => _CorpusImportDialogState();
}

class _CorpusImportDialogState extends State<CorpusImportDialog> {
  final List<XFile> _files = [];
  final Map<String, CorpusSummary> _validated = {};
  final Map<String, List<CorpusImportIssue>> _issues = {};
  bool _rightsConfirmed = false;
  bool _busy = false;
  bool _dragging = false;
  String? _error;

  bool get _canImport =>
      _rightsConfirmed &&
      _files.isNotEmpty &&
      _validated.length == _files.length &&
      _issues.isEmpty &&
      !_busy;

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).colorScheme;
    return AlertDialog(
      title: const Text('Import Markdown corpora'),
      content: SizedBox(
        width: 620,
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxHeight: 620),
          child: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Text(
                  'Drop one or more structured .md files. Each file is scoped '
                  'to a certification and an exact exam domain.',
                  style: Theme.of(context).textTheme.bodyLarge,
                ),
                const SizedBox(height: AppSpacing.md),
                DropTarget(
                  onDragEntered: (_) => setState(() => _dragging = true),
                  onDragExited: (_) => setState(() => _dragging = false),
                  onDragDone: (details) {
                    setState(() => _dragging = false);
                    _addFiles(details.files);
                  },
                  child: InkWell(
                    borderRadius: AppRadii.control,
                    onTap: _busy ? null : _pickFiles,
                    child: AnimatedContainer(
                      duration: const Duration(milliseconds: 160),
                      padding: const EdgeInsets.all(AppSpacing.xl),
                      decoration: BoxDecoration(
                        color: _dragging
                            ? colors.primaryContainer
                            : colors.surfaceContainerLow,
                        borderRadius: AppRadii.control,
                        border: Border.all(
                          color: _dragging ? colors.primary : colors.outline,
                          width: _dragging ? 2 : 1,
                        ),
                      ),
                      child: const Column(
                        children: [
                          Icon(Icons.upload_file_outlined, size: 36),
                          SizedBox(height: AppSpacing.sm),
                          Text(
                            'Drop Markdown files here',
                            style: TextStyle(fontWeight: FontWeight.w600),
                          ),
                          SizedBox(height: AppSpacing.xs),
                          Text('or click to choose files'),
                        ],
                      ),
                    ),
                  ),
                ),
                const SizedBox(height: AppSpacing.sm),
                TextButton.icon(
                  onPressed: _showFormat,
                  icon: const Icon(Icons.description_outlined),
                  label: const Text('View required Markdown format'),
                ),
                if (_files.isNotEmpty) ...[
                  const SizedBox(height: AppSpacing.sm),
                  ..._files.map(_fileTile),
                ],
                CheckboxListTile(
                  contentPadding: EdgeInsets.zero,
                  controlAffinity: ListTileControlAffinity.leading,
                  value: _rightsConfirmed,
                  onChanged: _busy
                      ? null
                      : (value) {
                          setState(() => _rightsConfirmed = value ?? false);
                          if (_rightsConfirmed && _files.isNotEmpty) {
                            _validateFiles();
                          }
                        },
                  title: const Text(
                    'I have the necessary rights to use this content.',
                  ),
                ),
                if (_error != null)
                  _ErrorPanel(message: _error!, issues: const []),
                if (_busy) ...[
                  const SizedBox(height: AppSpacing.sm),
                  const LinearProgressIndicator(),
                  const SizedBox(height: AppSpacing.xs),
                  Text(
                    _validated.length < _files.length
                        ? 'Validating structure and certification scope...'
                        : 'Rebuilding the local semantic index...',
                  ),
                ],
              ],
            ),
          ),
        ),
      ),
      actions: [
        TextButton(
          onPressed: _busy ? null : () => Navigator.of(context).pop(),
          child: const Text('Cancel'),
        ),
        FilledButton.icon(
          onPressed: _canImport ? _import : null,
          icon: const Icon(Icons.file_download_done_outlined),
          label: const Text('Import valid files'),
        ),
      ],
    );
  }

  Widget _fileTile(XFile file) {
    final summary = _validated[file.name];
    final issues = _issues[file.name] ?? const [];
    return Card(
      margin: const EdgeInsets.only(bottom: AppSpacing.sm),
      child: Column(
        children: [
          ListTile(
            leading: Icon(
              issues.isNotEmpty
                  ? Icons.error_outline
                  : summary != null
                      ? Icons.check_circle_outline
                      : Icons.pending_outlined,
              color: issues.isNotEmpty
                  ? Theme.of(context).colorScheme.error
                  : summary != null
                      ? Theme.of(context).colorScheme.primary
                      : null,
            ),
            title: Text(file.name),
            subtitle: summary == null
                ? const Text('Waiting for validation')
                : Text(
                    '${summary.certificationCode} • ${summary.domain}\n'
                    '${summary.chunkCount} semantic chunks',
                  ),
            isThreeLine: summary != null,
            trailing: IconButton(
              tooltip: 'Remove file',
              onPressed: _busy ? null : () => _removeFile(file),
              icon: const Icon(Icons.close),
            ),
          ),
          if (issues.isNotEmpty)
            Padding(
              padding: const EdgeInsets.fromLTRB(
                AppSpacing.md,
                0,
                AppSpacing.md,
                AppSpacing.md,
              ),
              child: _ErrorPanel(
                message: 'The file needs attention.',
                issues: issues,
              ),
            ),
        ],
      ),
    );
  }

  Future<void> _pickFiles() async {
    const group = XTypeGroup(label: 'Markdown corpus', extensions: ['md']);
    final files = await openFiles(acceptedTypeGroups: const [group]);
    if (!mounted || files.isEmpty) return;
    await _addFiles(files);
  }

  Future<void> _addFiles(Iterable<XFile> files) async {
    final allFiles = files.toList(growable: false);
    final accepted = allFiles
        .where((file) => file.name.toLowerCase().endsWith('.md'))
        .toList(growable: false);
    final rejected = allFiles.length - accepted.length;
    setState(() {
      for (final file in accepted) {
        final existing = _files.indexWhere((item) => item.name == file.name);
        if (existing >= 0) {
          _files[existing] = file;
        } else {
          _files.add(file);
        }
        _validated.remove(file.name);
        _issues.remove(file.name);
      }
      _error = rejected == 0
          ? null
          : '$rejected file(s) ignored. Only .md files are accepted.';
    });
    if (_rightsConfirmed && _files.isNotEmpty) await _validateFiles();
  }

  void _removeFile(XFile file) {
    setState(() {
      _files.remove(file);
      _validated.remove(file.name);
      _issues.remove(file.name);
    });
  }

  Future<void> _validateFiles() async {
    setState(() {
      _busy = true;
      _error = null;
      _validated.clear();
      _issues.clear();
    });
    for (final file in List<XFile>.from(_files)) {
      try {
        final summary = await widget.repository.validateMarkdownCorpus(
          filename: file.name,
          content: await file.readAsString(),
          rightsConfirmed: _rightsConfirmed,
        );
        if (mounted) setState(() => _validated[file.name] = summary);
      } on QuizApiException catch (exception) {
        if (!mounted) return;
        setState(() {
          _issues[file.name] = exception.issues.isEmpty
              ? [CorpusImportIssue(message: exception.message)]
              : exception.issues;
        });
      } catch (exception) {
        if (!mounted) return;
        setState(() {
          _issues[file.name] = [
            CorpusImportIssue(message: exception.toString())
          ];
        });
      }
    }
    final ownerByDocumentId = <String, String>{};
    for (final entry in _validated.entries) {
      final documentId = entry.value.documentId;
      if (documentId == null) continue;
      final firstOwner = ownerByDocumentId[documentId];
      if (firstOwner == null) {
        ownerByDocumentId[documentId] = entry.key;
        continue;
      }
      final issue = CorpusImportIssue(
        message: 'The document id `$documentId` is also used by another file.',
        hint: 'Give every imported corpus a unique document_id.',
      );
      _issues[firstOwner] = [issue];
      _issues[entry.key] = [issue];
    }
    if (mounted) setState(() => _busy = false);
  }

  Future<void> _import() async {
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final documents = <MarkdownCorpusDocument>[];
      for (final file in _files) {
        documents.add(MarkdownCorpusDocument(
          filename: file.name,
          content: await file.readAsString(),
        ));
      }
      final imported = await widget.repository.importMarkdownCorpora(
        files: documents,
        rightsConfirmed: _rightsConfirmed,
      );
      if (!mounted) return;
      Navigator.of(context).pop(CorpusSummary(
        title: imported.length == 1
            ? imported.first.title
            : '${imported.length} Markdown corpora',
        language: imported.length == 1 ? imported.first.language : 'multiple',
        chunkCount: imported.fold(0, (sum, item) => sum + item.chunkCount),
        certificationCode:
            imported.length == 1 ? imported.first.certificationCode : null,
        domain: imported.length == 1 ? imported.first.domain : null,
      ));
    } on QuizApiException catch (exception) {
      if (!mounted) return;
      setState(() {
        _busy = false;
        _error = exception.message;
      });
    } catch (exception) {
      if (!mounted) return;
      setState(() {
        _busy = false;
        _error = exception.toString();
      });
    }
  }

  void _showFormat() {
    showDialog<void>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Required Markdown format'),
        content: const SingleChildScrollView(
          child: SelectableText(_markdownExample),
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

class _ErrorPanel extends StatelessWidget {
  const _ErrorPanel({required this.message, required this.issues});

  final String message;
  final List<CorpusImportIssue> issues;

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).colorScheme;
    return Container(
      padding: const EdgeInsets.all(AppSpacing.md),
      decoration: BoxDecoration(
        color: colors.errorContainer,
        borderRadius: AppRadii.control,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(message, style: TextStyle(color: colors.onErrorContainer)),
          ...issues.map(
            (issue) => Padding(
              padding: const EdgeInsets.only(top: AppSpacing.xs),
              child: Text(
                '${issue.line == null ? '' : 'Line ${issue.line}: '}'
                '${issue.message}'
                '${issue.hint == null ? '' : '\n${issue.hint}'}',
                style: TextStyle(color: colors.onErrorContainer),
              ),
            ),
          ),
        ],
      ),
    );
  }
}
