import 'package:flutter/material.dart';

abstract final class AppTypography {
  static const String dataFamily = 'Doto';

  static TextStyle data({
    double fontSize = 32,
    FontWeight fontWeight = FontWeight.w600,
    Color? color,
    double height = 1,
  }) {
    return TextStyle(
      fontFamily: dataFamily,
      fontSize: fontSize,
      fontWeight: fontWeight,
      color: color,
      height: height,
      letterSpacing: -0.7,
    );
  }
}
