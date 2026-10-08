import 'package:flutter/material.dart';

import '../foundations/app_tokens.dart';

class AppBrandMark extends StatelessWidget {
  const AppBrandMark({super.key});

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Semantics(
      label: 'Quiz Machine',
      image: true,
      child: DecoratedBox(
        decoration: BoxDecoration(
          color: scheme.primary,
          borderRadius: AppRadii.control,
        ),
        child: SizedBox.square(
          dimension: 34,
          child: Icon(Icons.school_outlined, size: 20, color: scheme.onPrimary),
        ),
      ),
    );
  }
}
