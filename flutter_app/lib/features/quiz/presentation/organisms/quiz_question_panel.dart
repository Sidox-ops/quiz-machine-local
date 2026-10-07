import 'package:flutter/material.dart';

import '../../../../core/design_system/foundations/app_tokens.dart';
import '../../domain/quiz_models.dart';
import '../molecules/answer_option_tile.dart';
import '../molecules/quiz_progress_header.dart';
import '../view_models/quiz_view_model.dart';
import 'case_study_panel.dart';
import 'quiz_feedback_panel.dart';

class QuizQuestionPanel extends StatelessWidget {
  const QuizQuestionPanel({required this.viewModel, super.key});

  final QuizViewModel viewModel;

  @override
  Widget build(BuildContext context) {
    final question = viewModel.currentQuestion!;
    final result = viewModel.answerResult;

    return Column(
      key: ValueKey(question.questionId),
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        QuizProgressHeader(
          question: question,
          index: viewModel.currentIndex,
          total: viewModel.totalQuestions,
          progress: viewModel.sessionProgress,
        ),
        const SizedBox(height: AppSpacing.xl),
        if (question.caseStudy != null) ...[
          CaseStudyPanel(caseStudy: question.caseStudy!),
          const SizedBox(height: AppSpacing.xl),
        ],
        Text(question.question,
            style: Theme.of(context).textTheme.headlineSmall),
        const SizedBox(height: AppSpacing.lg),
        ...question.options.asMap().entries.map(
              (entry) => Padding(
                padding: const EdgeInsets.only(bottom: AppSpacing.sm),
                child: AnswerOptionTile(
                  option: entry.value,
                  presentationLabel: String.fromCharCode(65 + entry.key),
                  state: _optionState(entry.value, result),
                  onPressed: result == null
                      ? () => viewModel.selectOption(entry.value.id)
                      : null,
                ),
              ),
            ),
        const SizedBox(height: AppSpacing.sm),
        if (result == null)
          Align(
            alignment: Alignment.centerRight,
            child: FilledButton(
              onPressed:
                  viewModel.selectedOptionId == null || viewModel.checkingAnswer
                      ? null
                      : viewModel.submitAnswer,
              child: Text(
                viewModel.checkingAnswer ? 'Checking...' : 'Check answer',
              ),
            ),
          ),
        AnimatedSize(
          duration: AppMotion.resolve(context, AppMotion.standard),
          curve: AppMotion.enter,
          alignment: Alignment.topCenter,
          child: result == null
              ? const SizedBox.shrink()
              : QuizFeedbackPanel(
                  question: question,
                  result: result,
                  isLastQuestion:
                      viewModel.currentIndex + 1 >= viewModel.totalQuestions,
                  onNext: viewModel.nextQuestion,
                ),
        ),
      ],
    );
  }

  AnswerOptionState _optionState(
    QuizOption option,
    QuizAnswerResult? result,
  ) {
    if (result == null) {
      return option.id == viewModel.selectedOptionId
          ? AnswerOptionState.selected
          : AnswerOptionState.idle;
    }
    if (option.id == result.correctOptionId) {
      return AnswerOptionState.correct;
    }
    if (option.id == result.selectedOptionId) {
      return AnswerOptionState.incorrect;
    }
    return AnswerOptionState.muted;
  }
}
