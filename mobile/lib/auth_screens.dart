import 'dart:async';

import 'package:flutter/material.dart';

import 'data.dart';
import 'theme.dart';
import 'widgets.dart';

class SplashScreen extends StatefulWidget {
  const SplashScreen({super.key, required this.onComplete});
  final VoidCallback onComplete;

  @override
  State<SplashScreen> createState() => _SplashScreenState();
}

class _SplashScreenState extends State<SplashScreen> {
  Timer? timer;

  @override
  void initState() {
    super.initState();
    timer = Timer(const Duration(milliseconds: 1350), widget.onComplete);
  }

  @override
  void dispose() {
    timer?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Stack(
        fit: StackFit.expand,
        children: [
          CustomPaint(
            painter: FactoryScenePainter(
              channel: 5,
              active: true,
              light: false,
            ),
          ),
          const DecoratedBox(
            decoration: BoxDecoration(
              gradient: LinearGradient(
                begin: Alignment.topCenter,
                end: Alignment.bottomCenter,
                colors: [
                  Color(0xAA03101B),
                  Color(0xCC06131F),
                  Color(0xFF07131F),
                ],
              ),
            ),
          ),
          const SafeArea(
            child: Padding(
              padding: EdgeInsets.all(28),
              child: Column(
                children: [
                  Spacer(flex: 3),
                  AiVisionLogo(size: 108, showText: false),
                  SizedBox(height: 28),
                  Text(
                    'AI VISION',
                    style: TextStyle(
                      color: Colors.white,
                      fontSize: 31,
                      fontWeight: FontWeight.w900,
                      letterSpacing: 1.2,
                    ),
                  ),
                  SizedBox(height: 8),
                  Text(
                    'Smart Factory Vision System',
                    style: TextStyle(color: Color(0xFFB6C7D4)),
                  ),
                  Spacer(flex: 4),
                  LinearProgressIndicator(
                    minHeight: 3,
                    borderRadius: BorderRadius.all(Radius.circular(4)),
                    backgroundColor: Color(0x334CCBFF),
                  ),
                  SizedBox(height: 12),
                  Text(
                    'Loading intelligent operations…',
                    style: TextStyle(color: Color(0xFF91A7B7), fontSize: 11),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class OnboardingScreen extends StatelessWidget {
  const OnboardingScreen({
    super.key,
    required this.onComplete,
    required this.themeController,
  });

  final VoidCallback onComplete;
  final ThemeController themeController;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: LayoutBuilder(
          builder: (context, constraints) {
            final wide = constraints.maxWidth >= 780;
            final copy = Column(
              crossAxisAlignment:
                  wide ? CrossAxisAlignment.start : CrossAxisAlignment.center,
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                const AiVisionLogo(size: 38),
                const SizedBox(height: 42),
                Text(
                  'Smarter Production\nStarts Here',
                  textAlign: wide ? TextAlign.left : TextAlign.center,
                  style: Theme.of(context).textTheme.displaySmall?.copyWith(
                        fontWeight: FontWeight.w900,
                        height: 1.05,
                      ),
                ),
                const SizedBox(height: 18),
                Text(
                  'AI-powered monitoring, real-time alerts and production '
                  'analytics—always in your hand.',
                  textAlign: wide ? TextAlign.left : TextAlign.center,
                  style: TextStyle(
                    height: 1.55,
                    color: Theme.of(context).colorScheme.onSurfaceVariant,
                  ),
                ),
                const SizedBox(height: 30),
                Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  alignment: wide ? WrapAlignment.start : WrapAlignment.center,
                  children: const [
                    StatusPill(
                      label: 'LIVE MONITORING',
                      color: AppColors.cyan,
                      icon: Icons.videocam_outlined,
                    ),
                    StatusPill(
                      label: 'AI ALERTS',
                      color: AppColors.red,
                      icon: Icons.notifications_active_outlined,
                    ),
                    StatusPill(
                      label: 'ANALYTICS',
                      color: AppColors.green,
                      icon: Icons.insights_outlined,
                    ),
                  ],
                ),
              ],
            );

            final visual = Card(
              clipBehavior: Clip.antiAlias,
              child: Stack(
                fit: StackFit.expand,
                children: [
                  CustomPaint(
                    painter: FactoryScenePainter(
                      channel: 2,
                      active: true,
                      light: Theme.of(context).brightness == Brightness.light,
                    ),
                  ),
                  DecoratedBox(
                    decoration: BoxDecoration(
                      gradient: LinearGradient(
                        begin: Alignment.topLeft,
                        end: Alignment.bottomRight,
                        colors: [
                          AppColors.blue.withValues(alpha: .05),
                          AppColors.blue.withValues(alpha: .45),
                        ],
                      ),
                    ),
                  ),
                  const Center(
                    child: Icon(
                      Icons.phone_android_rounded,
                      color: Colors.white,
                      size: 112,
                    ),
                  ),
                ],
              ),
            );

            return Stack(
              children: [
                Padding(
                  padding: EdgeInsets.fromLTRB(
                    wide ? 56 : 24,
                    24,
                    wide ? 56 : 24,
                    90,
                  ),
                  child: wide
                      ? Row(
                          children: [
                            Expanded(child: copy),
                            const SizedBox(width: 44),
                            Expanded(child: visual),
                          ],
                        )
                      : Column(
                          children: [
                            Expanded(flex: 5, child: copy),
                            const SizedBox(height: 22),
                            Expanded(flex: 3, child: visual),
                          ],
                        ),
                ),
                Positioned(
                  top: 16,
                  right: 18,
                  child: ThemeToggleButton(controller: themeController),
                ),
                Positioned(
                  left: wide ? 56 : 24,
                  right: wide ? 56 : 24,
                  bottom: 24,
                  child: FilledButton(
                    onPressed: onComplete,
                    child: const Text('Continue'),
                  ),
                ),
              ],
            );
          },
        ),
      ),
    );
  }
}

class LoginScreen extends StatefulWidget {
  const LoginScreen({
    super.key,
    required this.onLogin,
    required this.themeController,
    required this.sessionController,
  });

  final VoidCallback onLogin;
  final ThemeController themeController;
  final SessionController sessionController;

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  late final TextEditingController server;
  final email = TextEditingController(text: 'admin@ai-vision.local');
  final password = TextEditingController();
  bool obscure = true;
  bool remember = true;

  @override
  void initState() {
    super.initState();
    server = TextEditingController(
      text: widget.sessionController.serverUrl,
    );
  }

  @override
  void dispose() {
    server.dispose();
    email.dispose();
    password.dispose();
    super.dispose();
  }

  Future<void> _login() async {
    FocusScope.of(context).unfocus();
    try {
      await widget.sessionController.login(
        server: server.text,
        email: email.text,
        password: password.text,
      );
      if (mounted) widget.onLogin();
    } catch (_) {
      // SessionController exposes a human-readable server error below.
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(24),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 460),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Row(
                    children: [
                      const AiVisionLogo(size: 36),
                      const Spacer(),
                      ThemeToggleButton(controller: widget.themeController),
                    ],
                  ),
                  const SizedBox(height: 48),
                  Text(
                    'Welcome Back!',
                    style: Theme.of(context).textTheme.headlineMedium?.copyWith(
                          fontWeight: FontWeight.w900,
                        ),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    'Sign in to continue to your factory.',
                    style: TextStyle(
                      color: Theme.of(context).colorScheme.onSurfaceVariant,
                    ),
                  ),
                  const SizedBox(height: 30),
                  TextField(
                    controller: server,
                    keyboardType: TextInputType.url,
                    textInputAction: TextInputAction.next,
                    autocorrect: false,
                    decoration: const InputDecoration(
                      labelText: 'AI Vision server',
                      hintText: 'https://your-server.example.com',
                      prefixIcon: Icon(Icons.dns_outlined),
                    ),
                  ),
                  const SizedBox(height: 14),
                  TextField(
                    controller: email,
                    keyboardType: TextInputType.emailAddress,
                    textInputAction: TextInputAction.next,
                    autocorrect: false,
                    decoration: const InputDecoration(
                      labelText: 'Email',
                      prefixIcon: Icon(Icons.mail_outline_rounded),
                    ),
                  ),
                  const SizedBox(height: 14),
                  TextField(
                    controller: password,
                    obscureText: obscure,
                    onSubmitted: (_) => _login(),
                    decoration: InputDecoration(
                      labelText: 'Password',
                      prefixIcon: const Icon(Icons.lock_outline_rounded),
                      suffixIcon: IconButton(
                        onPressed: () => setState(() => obscure = !obscure),
                        icon: Icon(
                          obscure
                              ? Icons.visibility_outlined
                              : Icons.visibility_off_outlined,
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(height: 8),
                  Row(
                    children: [
                      Checkbox(
                        value: remember,
                        onChanged: (value) =>
                            setState(() => remember = value ?? false),
                      ),
                      const Text('Remember me'),
                      const Spacer(),
                      TextButton(
                        onPressed: () {},
                        child: const Text('Forgot password?'),
                      ),
                    ],
                  ),
                  const SizedBox(height: 8),
                  ListenableBuilder(
                    listenable: widget.sessionController,
                    builder: (context, _) {
                      final controller = widget.sessionController;
                      return Column(
                        crossAxisAlignment: CrossAxisAlignment.stretch,
                        children: [
                          if (controller.error != null) ...[
                            Container(
                              padding: const EdgeInsets.all(12),
                              decoration: BoxDecoration(
                                color: AppColors.red.withValues(alpha: .12),
                                borderRadius: BorderRadius.circular(10),
                                border: Border.all(
                                  color: AppColors.red.withValues(alpha: .35),
                                ),
                              ),
                              child: Text(
                                controller.error!,
                                style: const TextStyle(
                                  color: AppColors.red,
                                  fontSize: 12,
                                ),
                              ),
                            ),
                            const SizedBox(height: 12),
                          ],
                          FilledButton.icon(
                            onPressed: controller.busy ? null : _login,
                            icon: controller.busy
                                ? const SizedBox.square(
                                    dimension: 18,
                                    child: CircularProgressIndicator(
                                      strokeWidth: 2,
                                    ),
                                  )
                                : const Icon(Icons.login_rounded),
                            label: Text(
                              controller.busy
                                  ? 'Connecting to AI Vision…'
                                  : 'Login',
                            ),
                          ),
                        ],
                      );
                    },
                  ),
                  const SizedBox(height: 28),
                  Row(
                    children: [
                      const Expanded(child: Divider()),
                      Padding(
                        padding: const EdgeInsets.symmetric(horizontal: 12),
                        child: Text(
                          'secure factory access',
                          style: TextStyle(
                            color: Theme.of(
                              context,
                            ).colorScheme.onSurfaceVariant,
                            fontSize: 11,
                          ),
                        ),
                      ),
                      const Expanded(child: Divider()),
                    ],
                  ),
                  const SizedBox(height: 20),
                  Row(
                    children: [
                      Expanded(
                        child: OutlinedButton.icon(
                          onPressed: () {},
                          icon: const Icon(Icons.fingerprint_rounded),
                          label: const Text('Biometric'),
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: OutlinedButton.icon(
                          onPressed: () {},
                          icon: const Icon(Icons.badge_outlined),
                          label: const Text('SSO'),
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
