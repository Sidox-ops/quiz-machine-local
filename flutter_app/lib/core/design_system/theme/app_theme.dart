import 'package:flutter/material.dart';

import '../foundations/app_tokens.dart';
import '../foundations/app_typography.dart';

abstract final class AppTheme {
  static ThemeData get light => _build(Brightness.light);
  static ThemeData get dark => _build(Brightness.dark);

  static ThemeData _build(Brightness brightness) {
    final isDark = brightness == Brightness.dark;
    final base = ColorScheme.fromSeed(
      seedColor: const Color(0xFF0B6B68),
      brightness: brightness,
    );
    final scheme = base.copyWith(
      secondary: isDark ? const Color(0xFFB9C4CE) : const Color(0xFF52616B),
      onSecondary: isDark ? const Color(0xFF263139) : Colors.white,
      tertiary: isDark ? const Color(0xFFFFB68D) : const Color(0xFFA94F24),
      onTertiary: isDark ? const Color(0xFF552008) : Colors.white,
      surface: isDark ? const Color(0xFF161A1B) : const Color(0xFFF9FAFA),
      surfaceContainerLowest: isDark ? const Color(0xFF101415) : Colors.white,
      surfaceContainerLow:
          isDark ? const Color(0xFF1D2223) : const Color(0xFFF1F4F4),
      outline: isDark ? const Color(0xFF7D8988) : const Color(0xFF72807F),
      outlineVariant:
          isDark ? const Color(0xFF3E4948) : const Color(0xFFCFD8D7),
    );

    final semanticColors = isDark
        ? const AppSemanticColors(
            success: Color(0xFF83D5AA),
            onSuccess: Color(0xFF003922),
            successContainer: Color(0xFF075135),
            onSuccessContainer: Color(0xFFA0F2C4),
            attention: Color(0xFFFFB68D),
            onAttention: Color(0xFF552008),
            attentionContainer: Color(0xFF773410),
            onAttentionContainer: Color(0xFFFFDBCA),
          )
        : const AppSemanticColors(
            success: Color(0xFF16663F),
            onSuccess: Colors.white,
            successContainer: Color(0xFFD6F5E2),
            onSuccessContainer: Color(0xFF0A3B25),
            attention: Color(0xFF9A461D),
            onAttention: Colors.white,
            attentionContainer: Color(0xFFFFDBCA),
            onAttentionContainer: Color(0xFF572005),
          );

    final textTheme = ThemeData(brightness: brightness).textTheme.copyWith(
          headlineMedium: const TextStyle(
            fontFamily: AppTypography.dataFamily,
            fontSize: 28,
            height: 1.2,
            fontWeight: FontWeight.w700,
            letterSpacing: 0,
          ),
          headlineSmall: const TextStyle(
            fontFamily: AppTypography.dataFamily,
            fontSize: 22,
            height: 1.3,
            fontWeight: FontWeight.w600,
            letterSpacing: 0,
          ),
          titleLarge: const TextStyle(
            fontFamily: AppTypography.dataFamily,
            fontSize: 18,
            height: 1.35,
            fontWeight: FontWeight.w600,
            letterSpacing: 0,
          ),
          titleMedium: const TextStyle(
            fontFamily: AppTypography.dataFamily,
            fontSize: 15,
            height: 1.35,
            fontWeight: FontWeight.w600,
            letterSpacing: 0,
          ),
          bodyLarge:
              const TextStyle(fontSize: 16, height: 1.5, letterSpacing: 0),
          bodyMedium:
              const TextStyle(fontSize: 14, height: 1.45, letterSpacing: 0),
          labelLarge: const TextStyle(
            fontSize: 14,
            fontWeight: FontWeight.w600,
            letterSpacing: 0,
          ),
          labelMedium: const TextStyle(
            fontFamily: AppTypography.dataFamily,
            fontSize: 12,
            fontWeight: FontWeight.w600,
            letterSpacing: 0.2,
          ),
        );

    final border = OutlineInputBorder(
      borderRadius: AppRadii.control,
      borderSide: BorderSide(color: scheme.outlineVariant),
    );

    return ThemeData(
      useMaterial3: true,
      brightness: brightness,
      colorScheme: scheme,
      scaffoldBackgroundColor: scheme.surface,
      textTheme: textTheme,
      extensions: [semanticColors],
      appBarTheme: AppBarTheme(
        elevation: 0,
        scrolledUnderElevation: 0,
        backgroundColor: scheme.surface,
        foregroundColor: scheme.onSurface,
        surfaceTintColor: Colors.transparent,
      ),
      dividerTheme: DividerThemeData(
        color: scheme.outlineVariant,
        thickness: 1,
        space: 1,
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: scheme.surfaceContainerLowest,
        border: border,
        enabledBorder: border,
        focusedBorder: border.copyWith(
          borderSide: BorderSide(color: scheme.primary, width: 2),
        ),
        contentPadding:
            const EdgeInsets.symmetric(horizontal: 12, vertical: 14),
      ),
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          minimumSize: const Size(48, 48),
          shape: const RoundedRectangleBorder(borderRadius: AppRadii.control),
          padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 14),
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          minimumSize: const Size(48, 48),
          shape: const RoundedRectangleBorder(borderRadius: AppRadii.control),
          padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 14),
        ),
      ),
      segmentedButtonTheme: SegmentedButtonThemeData(
        style: ButtonStyle(
          visualDensity: VisualDensity.standard,
          shape: const WidgetStatePropertyAll(
            RoundedRectangleBorder(borderRadius: AppRadii.control),
          ),
          minimumSize: const WidgetStatePropertyAll(Size(48, 44)),
        ),
      ),
      sliderTheme: SliderThemeData(
        activeTrackColor: scheme.primary,
        inactiveTrackColor: scheme.primaryContainer,
        thumbColor: scheme.primary,
        overlayColor: scheme.primary.withValues(alpha: 0.12),
        showValueIndicator: ShowValueIndicator.onlyForDiscrete,
      ),
      progressIndicatorTheme: ProgressIndicatorThemeData(
        color: scheme.primary,
        linearTrackColor: scheme.surfaceContainerLow,
        borderRadius: AppRadii.compact,
      ),
      tooltipTheme: TooltipThemeData(
        decoration: BoxDecoration(
          color: scheme.inverseSurface,
          borderRadius: AppRadii.compact,
        ),
        textStyle: TextStyle(color: scheme.onInverseSurface),
      ),
    );
  }
}
