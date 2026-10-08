import 'package:ai103_quiz_ui/features/setup/domain/setup_models.dart';
import 'package:flutter_test/flutter_test.dart';

Map<String, dynamic> _diagnostics({required bool connectionChecked}) => {
      'platform': 'macOS',
      'architecture': 'arm64',
      'ollama_installed': true,
      'ollama_reachable': true,
      'llm_model': 'qwen3:8b',
      'llm_ready': true,
      'embedding_model': 'nomic-embed-text',
      'embedding_ready': true,
      'index_ready': true,
      'indexed_chunks': 12,
      'knowledge_provider': 'microsoft_learn_mcp',
      'knowledge_ready': true,
      'knowledge_check_completed': connectionChecked,
      'free_disk_bytes': 20 * 1024 * 1024 * 1024,
      'recommended_free_bytes': 8 * 1024 * 1024 * 1024,
      'disk_ready': true,
      'physical_memory_bytes': 16 * 1024 * 1024 * 1024,
      'model_recommendation_reason': 'Best compatible model for this machine.',
      'ollama_models': [
        {
          'name': 'qwen3:8b',
          'size': 5 * 1024 * 1024 * 1024,
          'estimated_memory_bytes': 7 * 1024 * 1024 * 1024,
          'fits_memory': true,
          'compatible': true,
          'compatibility_reason': 'Compatible local chat model.',
          'probe_status': 'passed',
          'probe_duration_ms': 1250,
          'recommended': true,
          'selected': true,
        },
      ],
    };

void main() {
  test('cached Microsoft Learn data does not skip the onboarding check', () {
    final cachedOnly = SystemDiagnostics.fromJson(
      _diagnostics(connectionChecked: false),
    );
    final checked = SystemDiagnostics.fromJson(
      _diagnostics(connectionChecked: true),
    );

    expect(cachedOnly.knowledgeReady, isTrue);
    expect(cachedOnly.ready, isFalse);
    expect(checked.ready, isTrue);
    expect(checked.compatibleModels.single.fitsMemory, isTrue);
    expect(checked.compatibleModels.single.probeStatus, 'passed');
    expect(
        checked.compatibleModels.single.summary, contains('JSON test 1.3 s'));
  });
}
