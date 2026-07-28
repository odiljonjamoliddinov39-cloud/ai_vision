import 'package:ai_vision_mobile/main.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('launches and reaches onboarding', (tester) async {
    await tester.pumpWidget(const AiVisionBootstrap());
    expect(find.text('AI VISION'), findsOneWidget);

    await tester.pump(const Duration(milliseconds: 1400));
    await tester.pump(const Duration(milliseconds: 500));
    expect(find.text('Smarter Production\nStarts Here'), findsOneWidget);
    expect(find.text('Continue'), findsOneWidget);
  });

  testWidgets('theme toggle changes application brightness', (tester) async {
    await tester.pumpWidget(const AiVisionBootstrap());
    await tester.pump(const Duration(milliseconds: 1400));
    await tester.pump(const Duration(milliseconds: 500));

    final before = Theme.of(tester.element(find.text('Continue'))).brightness;
    await tester.tap(find.byTooltip('Light mode'));
    await tester.pump();
    final after = Theme.of(tester.element(find.text('Continue'))).brightness;

    expect(before, Brightness.dark);
    expect(after, Brightness.light);
  });
}
