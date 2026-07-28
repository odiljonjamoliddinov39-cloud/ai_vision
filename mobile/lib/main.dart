import 'package:flutter/material.dart';

import 'app_shell.dart';
import 'auth_screens.dart';
import 'data.dart';
import 'theme.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const AiVisionBootstrap());
}

class AiVisionBootstrap extends StatefulWidget {
  const AiVisionBootstrap({super.key});

  @override
  State<AiVisionBootstrap> createState() => _AiVisionBootstrapState();
}

class _AiVisionBootstrapState extends State<AiVisionBootstrap> {
  final ThemeController themeController = ThemeController();
  final SessionController sessionController = SessionController();

  @override
  void dispose() {
    themeController.dispose();
    sessionController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: themeController,
      builder: (context, _) {
        return MaterialApp(
          title: 'AI Vision',
          debugShowCheckedModeBanner: false,
          theme: AppTheme.light(),
          darkTheme: AppTheme.dark(),
          themeMode: themeController.mode,
          restorationScopeId: 'ai_vision_mobile',
          home: LaunchFlow(
            themeController: themeController,
            sessionController: sessionController,
          ),
        );
      },
    );
  }
}

class LaunchFlow extends StatefulWidget {
  const LaunchFlow({
    super.key,
    required this.themeController,
    required this.sessionController,
  });

  final ThemeController themeController;
  final SessionController sessionController;

  @override
  State<LaunchFlow> createState() => _LaunchFlowState();
}

class _LaunchFlowState extends State<LaunchFlow> {
  int stage = 0;

  @override
  Widget build(BuildContext context) {
    return AnimatedSwitcher(
      duration: const Duration(milliseconds: 420),
      switchInCurve: Curves.easeOutCubic,
      switchOutCurve: Curves.easeInCubic,
      child: switch (stage) {
        0 => SplashScreen(
            key: const ValueKey('splash'),
            onComplete: () => setState(() => stage = 1),
          ),
        1 => OnboardingScreen(
            key: const ValueKey('onboarding'),
            themeController: widget.themeController,
            onComplete: () => setState(() => stage = 2),
          ),
        2 => LoginScreen(
            key: const ValueKey('login'),
            themeController: widget.themeController,
            sessionController: widget.sessionController,
            onLogin: () => setState(() => stage = 3),
          ),
        _ => AppShell(
            key: const ValueKey('app'),
            themeController: widget.themeController,
            sessionController: widget.sessionController,
            onLogout: () {
              widget.sessionController.logout();
              setState(() => stage = 2);
            },
          ),
      },
    );
  }
}
