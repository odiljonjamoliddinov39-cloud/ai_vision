import 'dart:math' as math;

import 'dart:async';

import 'package:flutter/material.dart';

import 'data.dart';
import 'theme.dart';

class AiVisionLogo extends StatelessWidget {
  const AiVisionLogo({super.key, this.size = 48, this.showText = true});

  final double size;
  final bool showText;

  @override
  Widget build(BuildContext context) {
    final logo = SizedBox.square(
      dimension: size,
      child: Stack(
        alignment: Alignment.center,
        children: [
          Container(
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              gradient: const SweepGradient(
                colors: [
                  AppColors.cyan,
                  AppColors.blue,
                  Color(0xFF7AE5FF),
                  AppColors.cyan,
                ],
              ),
              boxShadow: [
                BoxShadow(
                  color: AppColors.blue.withValues(alpha: .35),
                  blurRadius: size * .3,
                ),
              ],
            ),
          ),
          Container(
            width: size * .62,
            height: size * .62,
            decoration: BoxDecoration(
              color: Theme.of(context).scaffoldBackgroundColor,
              shape: BoxShape.circle,
            ),
          ),
          Icon(
            Icons.visibility_rounded,
            size: size * .52,
            color: AppColors.cyan,
          ),
        ],
      ),
    );

    if (!showText) return logo;
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        logo,
        const SizedBox(width: 12),
        Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(
              'AI VISION',
              style: TextStyle(
                fontSize: size * .40,
                fontWeight: FontWeight.w900,
                letterSpacing: .4,
                height: 1,
              ),
            ),
            const SizedBox(height: 4),
            Text(
              'Smart Factory Vision System',
              style: TextStyle(
                color: Theme.of(context).colorScheme.onSurfaceVariant,
                fontSize: math.max(9.0, size * .17).toDouble(),
              ),
            ),
          ],
        ),
      ],
    );
  }
}

class ThemeToggleButton extends StatelessWidget {
  const ThemeToggleButton({
    super.key,
    required this.controller,
    this.label = false,
  });

  final ThemeController controller;
  final bool label;

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: controller,
      builder: (context, _) {
        final text = controller.isDark ? 'Light mode' : 'Dark mode';
        if (label) {
          return ListTile(
            leading: Icon(
              controller.isDark
                  ? Icons.light_mode_outlined
                  : Icons.dark_mode_outlined,
            ),
            title: Text(text),
            trailing: Switch(
              value: !controller.isDark,
              onChanged: (_) => controller.toggle(),
            ),
            onTap: controller.toggle,
          );
        }
        return IconButton.filledTonal(
          tooltip: text,
          onPressed: controller.toggle,
          icon: Icon(
            controller.isDark
                ? Icons.light_mode_outlined
                : Icons.dark_mode_outlined,
          ),
        );
      },
    );
  }
}

class PageHeading extends StatelessWidget {
  const PageHeading({
    super.key,
    required this.title,
    this.subtitle,
    this.trailing,
  });

  final String title;
  final String? subtitle;
  final Widget? trailing;

  @override
  Widget build(BuildContext context) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                title,
                style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                      fontWeight: FontWeight.w800,
                    ),
              ),
              if (subtitle != null) ...[
                const SizedBox(height: 5),
                Text(
                  subtitle!,
                  style: TextStyle(
                    color: Theme.of(context).colorScheme.onSurfaceVariant,
                  ),
                ),
              ],
            ],
          ),
        ),
        if (trailing != null) trailing!,
      ],
    );
  }
}

class StatusPill extends StatelessWidget {
  const StatusPill({
    super.key,
    required this.label,
    required this.color,
    this.icon,
  });

  final String label;
  final Color color;
  final IconData? icon;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 5),
      decoration: BoxDecoration(
        color: color.withValues(alpha: .15),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: color.withValues(alpha: .35)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (icon != null) ...[
            Icon(icon, color: color, size: 13),
            const SizedBox(width: 5),
          ] else ...[
            Container(
              width: 7,
              height: 7,
              decoration: BoxDecoration(color: color, shape: BoxShape.circle),
            ),
            const SizedBox(width: 6),
          ],
          Text(
            label,
            style: TextStyle(
              color: color,
              fontSize: 11,
              fontWeight: FontWeight.w800,
            ),
          ),
        ],
      ),
    );
  }
}

class MetricCard extends StatelessWidget {
  const MetricCard({
    super.key,
    required this.label,
    required this.value,
    required this.icon,
    required this.color,
    this.caption,
  });

  final String label;
  final String value;
  final String? caption;
  final IconData icon;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Container(
                  width: 36,
                  height: 36,
                  decoration: BoxDecoration(
                    color: color.withValues(alpha: .14),
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: Icon(icon, color: color, size: 20),
                ),
                const Spacer(),
                Icon(
                  Icons.north_east_rounded,
                  size: 15,
                  color: Theme.of(context).colorScheme.onSurfaceVariant,
                ),
              ],
            ),
            const SizedBox(height: 14),
            Text(
              value,
              style: Theme.of(
                context,
              ).textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.w900),
            ),
            const SizedBox(height: 3),
            Text(
              label,
              style: TextStyle(
                color: Theme.of(context).colorScheme.onSurfaceVariant,
              ),
            ),
            if (caption != null) ...[
              const SizedBox(height: 3),
              Text(
                caption!,
                style: TextStyle(
                  color: color,
                  fontSize: 11,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class CameraCard extends StatelessWidget {
  const CameraCard({
    super.key,
    required this.camera,
    this.onTap,
    this.compact = false,
  });

  final CameraInfo camera;
  final VoidCallback? onTap;
  final bool compact;

  @override
  Widget build(BuildContext context) {
    return Card(
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: onTap,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Expanded(
              child: Stack(
                fit: StackFit.expand,
                children: [
                  if (camera.snapshotUrl != null && camera.online)
                    _LiveCameraImage(
                      url: camera.snapshotUrl!,
                      headers: camera.snapshotHeaders,
                      channel: camera.channel,
                    )
                  else
                    CustomPaint(
                      painter: FactoryScenePainter(
                        channel: camera.channel,
                        active: camera.online,
                        light: Theme.of(context).brightness == Brightness.light,
                      ),
                    ),
                  Positioned(
                    left: 10,
                    top: 10,
                    child: StatusPill(
                      label: camera.online ? 'LIVE' : 'OFFLINE',
                      color: camera.online ? AppColors.green : AppColors.red,
                    ),
                  ),
                  Positioned(
                    right: 10,
                    top: 10,
                    child: Container(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 7,
                        vertical: 4,
                      ),
                      decoration: BoxDecoration(
                        color: Colors.black.withValues(alpha: .58),
                        borderRadius: BorderRadius.circular(6),
                      ),
                      child: Text(
                        'CH ${camera.channel.toString().padLeft(2, '0')}',
                        style: const TextStyle(
                          color: Colors.white,
                          fontSize: 10,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                    ),
                  ),
                  if (camera.highlight)
                    Positioned(
                      left: 30,
                      bottom: 22,
                      child: Container(
                        width: 62,
                        height: 42,
                        decoration: BoxDecoration(
                          border: Border.all(color: AppColors.amber, width: 2),
                          borderRadius: BorderRadius.circular(4),
                        ),
                        child: const Align(
                          alignment: Alignment.topLeft,
                          child: ColoredBox(
                            color: AppColors.amber,
                            child: Padding(
                              padding: EdgeInsets.symmetric(
                                horizontal: 4,
                                vertical: 2,
                              ),
                              child: Text(
                                'BOX 94%',
                                style: TextStyle(
                                  color: Colors.black,
                                  fontSize: 8,
                                  fontWeight: FontWeight.w900,
                                ),
                              ),
                            ),
                          ),
                        ),
                      ),
                    ),
                ],
              ),
            ),
            Padding(
              padding: EdgeInsets.all(compact ? 9 : 12),
              child: Row(
                children: [
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          camera.name,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: TextStyle(
                            fontSize: compact ? 11 : 13,
                            fontWeight: FontWeight.w800,
                          ),
                        ),
                        const SizedBox(height: 3),
                        Text(
                          camera.location,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: TextStyle(
                            fontSize: compact ? 9 : 11,
                            color: Theme.of(
                              context,
                            ).colorScheme.onSurfaceVariant,
                          ),
                        ),
                      ],
                    ),
                  ),
                  Icon(
                    Icons.open_in_full_rounded,
                    size: 16,
                    color: Theme.of(context).colorScheme.onSurfaceVariant,
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _LiveCameraImage extends StatefulWidget {
  const _LiveCameraImage({
    required this.url,
    required this.headers,
    required this.channel,
  });

  final String url;
  final Map<String, String> headers;
  final int channel;

  @override
  State<_LiveCameraImage> createState() => _LiveCameraImageState();
}

class _LiveCameraImageState extends State<_LiveCameraImage> {
  Timer? _timer;
  int _cacheKey = DateTime.now().millisecondsSinceEpoch;

  @override
  void initState() {
    super.initState();
    _timer = Timer.periodic(const Duration(seconds: 1), (_) {
      if (mounted) {
        setState(() => _cacheKey = DateTime.now().millisecondsSinceEpoch);
      }
    });
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final source = Uri.parse(widget.url);
    final uri = source.replace(
      queryParameters: {
        ...source.queryParameters,
        't': '$_cacheKey',
      },
    );
    return Image.network(
      uri.toString(),
      headers: widget.headers,
      fit: BoxFit.cover,
      gaplessPlayback: true,
      filterQuality: FilterQuality.low,
      errorBuilder: (context, error, stackTrace) {
        return CustomPaint(
          painter: FactoryScenePainter(
            channel: widget.channel,
            active: false,
            light: Theme.of(context).brightness == Brightness.light,
          ),
          child: const Center(
            child: StatusPill(
              label: 'WAITING FOR FRAME',
              color: AppColors.amber,
            ),
          ),
        );
      },
    );
  }
}

class AlertTile extends StatelessWidget {
  const AlertTile({super.key, required this.alert, this.trailing = true});

  final AlertInfo alert;
  final bool trailing;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: ListTile(
        minVerticalPadding: 12,
        contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 5),
        leading: Container(
          width: 42,
          height: 42,
          decoration: BoxDecoration(
            color: alert.color.withValues(alpha: .15),
            borderRadius: BorderRadius.circular(11),
          ),
          child: Icon(alert.icon, color: alert.color, size: 21),
        ),
        title: Text(
          alert.title,
          style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w800),
        ),
        subtitle: Padding(
          padding: const EdgeInsets.only(top: 4),
          child: Text(
            alert.location,
            style: TextStyle(
              fontSize: 11,
              color: Theme.of(context).colorScheme.onSurfaceVariant,
            ),
          ),
        ),
        trailing: trailing
            ? Text(
                alert.time,
                style: TextStyle(
                  fontSize: 10,
                  color: Theme.of(context).colorScheme.onSurfaceVariant,
                ),
              )
            : null,
      ),
    );
  }
}

class MachineTile extends StatelessWidget {
  const MachineTile({super.key, required this.machine});

  final MachineInfo machine;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Row(
          children: [
            Container(
              width: 48,
              height: 48,
              decoration: BoxDecoration(
                color: machine.color.withValues(alpha: .13),
                borderRadius: BorderRadius.circular(12),
              ),
              child: Icon(
                Icons.precision_manufacturing_outlined,
                color: machine.color,
              ),
            ),
            const SizedBox(width: 13),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    machine.name,
                    style: const TextStyle(fontWeight: FontWeight.w800),
                  ),
                  const SizedBox(height: 6),
                  Row(
                    children: [
                      StatusPill(label: machine.status, color: machine.color),
                      const SizedBox(width: 10),
                      Text(
                        'Speed ${machine.speed}%',
                        style: TextStyle(
                          color: Theme.of(context).colorScheme.onSurfaceVariant,
                          fontSize: 11,
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),
            Column(
              crossAxisAlignment: CrossAxisAlignment.end,
              children: [
                Text(
                  machine.oee == 0 ? '—' : '${machine.oee}%',
                  style: TextStyle(
                    color: machine.color,
                    fontSize: 19,
                    fontWeight: FontWeight.w900,
                  ),
                ),
                const Text('OEE', style: TextStyle(fontSize: 10)),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class DonutChart extends StatelessWidget {
  const DonutChart({
    super.key,
    required this.value,
    required this.color,
    this.size = 120,
    this.label,
  });

  final double value;
  final Color color;
  final double size;
  final String? label;

  @override
  Widget build(BuildContext context) {
    return SizedBox.square(
      dimension: size,
      child: Stack(
        alignment: Alignment.center,
        children: [
          CustomPaint(
            size: Size.square(size),
            painter: DonutPainter(
              value: value,
              color: color,
              trackColor: Theme.of(context).dividerColor,
            ),
          ),
          Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(
                '${(value * 100).round()}%',
                style: TextStyle(
                  fontSize: size * .20,
                  fontWeight: FontWeight.w900,
                ),
              ),
              if (label != null)
                Text(
                  label!,
                  style: TextStyle(
                    fontSize: size * .08,
                    color: Theme.of(context).colorScheme.onSurfaceVariant,
                  ),
                ),
            ],
          ),
        ],
      ),
    );
  }
}

class DonutPainter extends CustomPainter {
  DonutPainter({
    required this.value,
    required this.color,
    required this.trackColor,
  });

  final double value;
  final Color color;
  final Color trackColor;

  @override
  void paint(Canvas canvas, Size size) {
    final center = Offset(size.width / 2, size.height / 2);
    final radius = math.min(size.width, size.height) / 2 - 7;
    final rect = Rect.fromCircle(center: center, radius: radius);
    final track = Paint()
      ..color = trackColor
      ..style = PaintingStyle.stroke
      ..strokeWidth = 8;
    final active = Paint()
      ..color = color
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round
      ..strokeWidth = 8;
    canvas.drawArc(rect, 0, math.pi * 2, false, track);
    canvas.drawArc(
      rect,
      -math.pi / 2,
      math.pi * 2 * value.clamp(0, 1),
      false,
      active,
    );
  }

  @override
  bool shouldRepaint(covariant DonutPainter oldDelegate) =>
      oldDelegate.value != value ||
      oldDelegate.color != color ||
      oldDelegate.trackColor != trackColor;
}

class ProductionBars extends StatelessWidget {
  const ProductionBars({super.key, this.height = 160});
  final double height;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: height,
      width: double.infinity,
      child: CustomPaint(
        painter: BarChartPainter(
          color: AppColors.blue,
          secondary: AppColors.cyan,
          grid: Theme.of(context).dividerColor,
          label: Theme.of(context).colorScheme.onSurfaceVariant,
        ),
      ),
    );
  }
}

class BarChartPainter extends CustomPainter {
  BarChartPainter({
    required this.color,
    required this.secondary,
    required this.grid,
    required this.label,
  });

  final Color color;
  final Color secondary;
  final Color grid;
  final Color label;

  static const values = [
    .28,
    .46,
    .38,
    .61,
    .52,
    .82,
    .68,
    .94,
    .73,
    .87,
    .56,
    .70,
  ];

  @override
  void paint(Canvas canvas, Size size) {
    final chart = Rect.fromLTWH(4, 8, size.width - 8, size.height - 28);
    final gridPaint = Paint()
      ..color = grid.withValues(alpha: .75)
      ..strokeWidth = 1;
    for (var i = 0; i <= 4; i++) {
      final y = chart.top + chart.height * i / 4;
      canvas.drawLine(Offset(chart.left, y), Offset(chart.right, y), gridPaint);
    }

    final groupWidth = chart.width / values.length;
    for (var i = 0; i < values.length; i++) {
      final barWidth = groupWidth * .34;
      final x = chart.left + i * groupWidth + groupWidth * .15;
      final planHeight = chart.height * values[i];
      final actual = values[i] * (.82 + (i % 3) * .05);
      final actualHeight = chart.height * actual;
      final radius = const Radius.circular(3);
      canvas.drawRRect(
        RRect.fromRectAndRadius(
          Rect.fromLTWH(x, chart.bottom - planHeight, barWidth, planHeight),
          radius,
        ),
        Paint()..color = color.withValues(alpha: .45),
      );
      canvas.drawRRect(
        RRect.fromRectAndRadius(
          Rect.fromLTWH(
            x + barWidth + 2,
            chart.bottom - actualHeight,
            barWidth,
            actualHeight,
          ),
          radius,
        ),
        Paint()..color = secondary,
      );
    }
  }

  @override
  bool shouldRepaint(covariant BarChartPainter oldDelegate) =>
      oldDelegate.color != color ||
      oldDelegate.secondary != secondary ||
      oldDelegate.grid != grid;
}

class FactoryScenePainter extends CustomPainter {
  FactoryScenePainter({
    required this.channel,
    required this.active,
    required this.light,
  });

  final int channel;
  final bool active;
  final bool light;

  @override
  void paint(Canvas canvas, Size size) {
    final background = Paint()
      ..shader = LinearGradient(
        begin: Alignment.topLeft,
        end: Alignment.bottomRight,
        colors: active
            ? [
                const Color(0xFF203745),
                const Color(0xFF0C1821),
                const Color(0xFF193745),
              ]
            : [const Color(0xFF262E34), const Color(0xFF11171C)],
      ).createShader(Offset.zero & size);
    canvas.drawRect(Offset.zero & size, background);

    final random = math.Random(channel);
    final floor = Path()
      ..moveTo(0, size.height * .55)
      ..lineTo(size.width, size.height * .43)
      ..lineTo(size.width, size.height)
      ..lineTo(0, size.height)
      ..close();
    canvas.drawPath(
      floor,
      Paint()..color = const Color(0xFF253540).withValues(alpha: .85),
    );

    final beam = Paint()
      ..color = const Color(0xFF7B99A7).withValues(alpha: active ? .28 : .12)
      ..strokeWidth = 2;
    for (var i = 0; i < 7; i++) {
      final x = size.width * i / 6;
      canvas.drawLine(Offset(x, 0), Offset(x * .82 + 12, size.height), beam);
    }
    for (var i = 0; i < 5; i++) {
      final y = size.height * i / 8;
      canvas.drawLine(Offset(0, y), Offset(size.width, y + 12), beam);
    }

    for (var i = 0; i < 7; i++) {
      final x = random.nextDouble() * size.width * .85;
      final y = size.height * (.48 + random.nextDouble() * .32);
      final w = size.width * (.07 + random.nextDouble() * .09);
      final h = size.height * (.09 + random.nextDouble() * .17);
      canvas.drawRRect(
        RRect.fromRectAndRadius(
          Rect.fromLTWH(x, y, w, h),
          const Radius.circular(3),
        ),
        Paint()
          ..color = [
            const Color(0xFFE0A84A),
            const Color(0xFF4B7486),
            const Color(0xFF718A53),
            const Color(0xFF985A44),
          ][i % 4]
              .withValues(alpha: active ? .9 : .25),
      );
    }

    if (!active) {
      canvas.drawRect(
        Offset.zero & size,
        Paint()..color = Colors.black.withValues(alpha: .55),
      );
      final icon = TextPainter(
        text: const TextSpan(
          text: 'NO SIGNAL',
          style: TextStyle(
            color: Colors.white54,
            fontSize: 13,
            fontWeight: FontWeight.w800,
            letterSpacing: 2,
          ),
        ),
        textDirection: TextDirection.ltr,
      )..layout();
      icon.paint(
        canvas,
        Offset((size.width - icon.width) / 2, (size.height - icon.height) / 2),
      );
    }
  }

  @override
  bool shouldRepaint(covariant FactoryScenePainter oldDelegate) =>
      oldDelegate.channel != channel ||
      oldDelegate.active != active ||
      oldDelegate.light != light;
}

class ContentFrame extends StatelessWidget {
  const ContentFrame({super.key, required this.child});
  final Widget child;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 1260),
        child: Padding(
          padding: EdgeInsets.symmetric(
            horizontal: MediaQuery.sizeOf(context).width < 600 ? 16 : 24,
            vertical: 20,
          ),
          child: child,
        ),
      ),
    );
  }
}
