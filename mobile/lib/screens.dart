import 'package:flutter/material.dart';

import 'app_shell.dart';
import 'data.dart';
import 'theme.dart';
import 'widgets.dart';

class DashboardScreen extends StatelessWidget {
  const DashboardScreen({
    super.key,
    required this.onNavigate,
    required this.sessionController,
  });
  final ValueChanged<AppSection> onNavigate;
  final SessionController sessionController;

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      child: ContentFrame(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            PageHeading(
              title: 'Factory Overview',
              subtitle: sessionController.connected
                  ? 'Connected to ${sessionController.serverUrl}'
                  : 'Backend connection unavailable',
              trailing: _FactorySelector(),
            ),
            const SizedBox(height: 18),
            _OverallStatusCard(onCameras: () => onNavigate(AppSection.cameras)),
            const SizedBox(height: 14),
            _MetricGrid(
              children: [
                MetricCard(
                  label: 'Cameras',
                  value: '${sessionController.liveCameras.length}',
                  caption: '${sessionController.onlineCameraCount} online',
                  icon: Icons.videocam_outlined,
                  color: AppColors.blue,
                ),
                MetricCard(
                  label: 'Detections',
                  value: '${sessionController.detectionCount}',
                  caption: 'latest detector cycle',
                  icon: Icons.center_focus_strong_outlined,
                  color: AppColors.cyan,
                ),
                MetricCard(
                  label: 'Tracked',
                  value: '${sessionController.trackedCount}',
                  caption: 'unique live tracks',
                  icon: Icons.track_changes_outlined,
                  color: AppColors.purple,
                ),
                MetricCard(
                  label: 'Frames',
                  value: '${sessionController.framesRead}',
                  caption: 'processed by backend',
                  icon: Icons.movie_filter_outlined,
                  color: AppColors.green,
                ),
              ],
            ),
            const SizedBox(height: 14),
            LayoutBuilder(
              builder: (context, constraints) {
                final wide = constraints.maxWidth >= 820;
                final production = _ProductionCard(
                  onAnalytics: () => onNavigate(AppSection.analytics),
                );
                final alertList = _DashboardAlerts(
                  onOpen: () => onNavigate(AppSection.alerts),
                );
                if (wide) {
                  return Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Expanded(flex: 6, child: production),
                      const SizedBox(width: 14),
                      Expanded(flex: 4, child: alertList),
                    ],
                  );
                }
                return Column(
                  children: [production, const SizedBox(height: 14), alertList],
                );
              },
            ),
            const SizedBox(height: 24),
          ],
        ),
      ),
    );
  }
}

class _FactorySelector extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Container(
      constraints: const BoxConstraints(maxWidth: 180),
      child: DropdownButtonFormField<String>(
        initialValue: 'Main Factory',
        isDense: true,
        decoration: const InputDecoration(
          contentPadding: EdgeInsets.symmetric(horizontal: 12, vertical: 10),
        ),
        items: const [
          DropdownMenuItem(value: 'Main Factory', child: Text('Main Factory')),
          DropdownMenuItem(value: 'Factory 2', child: Text('Factory 2')),
        ],
        onChanged: (_) {},
      ),
    );
  }
}

class _OverallStatusCard extends StatelessWidget {
  const _OverallStatusCard({required this.onCameras});
  final VoidCallback onCameras;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(18),
        child: Row(
          children: [
            Container(
              width: 52,
              height: 52,
              decoration: BoxDecoration(
                color: AppColors.green.withValues(alpha: .12),
                borderRadius: BorderRadius.circular(14),
              ),
              child: const Icon(Icons.factory_outlined, color: AppColors.green),
            ),
            const SizedBox(width: 14),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Overall Status',
                    style: TextStyle(
                      color: Theme.of(context).colorScheme.onSurfaceVariant,
                      fontSize: 12,
                    ),
                  ),
                  const SizedBox(height: 3),
                  const Text(
                    'Good',
                    style: TextStyle(
                      color: AppColors.green,
                      fontSize: 23,
                      fontWeight: FontWeight.w900,
                    ),
                  ),
                  const Text(
                    'All critical systems operational',
                    style: TextStyle(fontSize: 11),
                  ),
                ],
              ),
            ),
            InkWell(
              borderRadius: BorderRadius.circular(70),
              onTap: onCameras,
              child: const DonutChart(
                value: .92,
                color: AppColors.green,
                size: 82,
                label: 'health',
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _MetricGrid extends StatelessWidget {
  const _MetricGrid({required this.children});
  final List<Widget> children;

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final columns = constraints.maxWidth >= 980
            ? 4
            : constraints.maxWidth >= 560
                ? 2
                : 2;
        final width = (constraints.maxWidth - 14 * (columns - 1)) / columns;
        return Wrap(
          spacing: 14,
          runSpacing: 14,
          children: children
              .map((child) => SizedBox(width: width, child: child))
              .toList(),
        );
      },
    );
  }
}

class _ProductionCard extends StatelessWidget {
  const _ProductionCard({required this.onAnalytics});
  final VoidCallback onAnalytics;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(18),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Row(
              children: [
                const Expanded(
                  child: Text(
                    'Today’s Production',
                    style: TextStyle(fontWeight: FontWeight.w800),
                  ),
                ),
                TextButton(
                  onPressed: onAnalytics,
                  child: const Text('View analytics'),
                ),
              ],
            ),
            const SizedBox(height: 12),
            const Row(
              children: [
                Expanded(
                  child: _DataPoint(
                    label: 'Plan',
                    value: '1,250',
                    color: AppColors.blue,
                  ),
                ),
                Expanded(
                  child: _DataPoint(
                    label: 'Actual',
                    value: '1,086',
                    color: AppColors.cyan,
                  ),
                ),
                Expanded(
                  child: _DataPoint(
                    label: 'Progress',
                    value: '86%',
                    color: AppColors.green,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 16),
            const ProductionBars(height: 150),
          ],
        ),
      ),
    );
  }
}

class _DataPoint extends StatelessWidget {
  const _DataPoint({
    required this.label,
    required this.value,
    required this.color,
  });

  final String label;
  final String value;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          label,
          style: TextStyle(
            color: Theme.of(context).colorScheme.onSurfaceVariant,
            fontSize: 11,
          ),
        ),
        const SizedBox(height: 4),
        Text(
          value,
          style: TextStyle(
            color: color,
            fontSize: 20,
            fontWeight: FontWeight.w900,
          ),
        ),
      ],
    );
  }
}

class _DashboardAlerts extends StatelessWidget {
  const _DashboardAlerts({required this.onOpen});
  final VoidCallback onOpen;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(18),
        child: Column(
          children: [
            Row(
              children: [
                const Expanded(
                  child: Text(
                    'Recent Alerts',
                    style: TextStyle(fontWeight: FontWeight.w800),
                  ),
                ),
                TextButton(onPressed: onOpen, child: const Text('View all')),
              ],
            ),
            const SizedBox(height: 8),
            for (final alert in alerts.take(3)) ...[
              AlertTile(alert: alert),
              const SizedBox(height: 8),
            ],
          ],
        ),
      ),
    );
  }
}

class CamerasScreen extends StatefulWidget {
  const CamerasScreen({
    super.key,
    required this.sessionController,
  });

  final SessionController sessionController;

  @override
  State<CamerasScreen> createState() => _CamerasScreenState();
}

class _CamerasScreenState extends State<CamerasScreen> {
  String filter = 'All';

  @override
  Widget build(BuildContext context) {
    final cameras = widget.sessionController.liveCameras;
    final visible = filter == 'Offline'
        ? cameras.where((camera) => !camera.online).toList()
        : filter == 'Production'
            ? cameras
                .where((camera) => camera.location == 'Production Hall')
                .toList()
            : cameras;

    return SingleChildScrollView(
      child: ContentFrame(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            PageHeading(
              title: 'Live Cameras',
              subtitle: '${widget.sessionController.onlineCameraCount} of '
                  '${cameras.length} cameras online · '
                  '${widget.sessionController.serverUrl}',
              trailing: IconButton.filledTonal(
                tooltip: 'Refresh cameras',
                onPressed: widget.sessionController.busy
                    ? null
                    : widget.sessionController.refresh,
                icon: const Icon(Icons.refresh_rounded),
              ),
            ),
            const SizedBox(height: 16),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                for (final item in ['All', 'Production', 'Offline'])
                  ChoiceChip(
                    label: Text(switch (item) {
                      'All' => 'All (${cameras.length})',
                      'Production' =>
                        'Production (${cameras.where((camera) => camera.location == 'Production Hall').length})',
                      _ =>
                        'Offline (${cameras.where((camera) => !camera.online).length})',
                    }),
                    selected: filter == item,
                    onSelected: (_) => setState(() => filter = item),
                  ),
                const SizedBox(width: 4),
                IconButton.filledTonal(
                  tooltip: 'Grid options',
                  onPressed: () {},
                  icon: const Icon(Icons.grid_view_rounded),
                ),
              ],
            ),
            const SizedBox(height: 16),
            if (visible.isEmpty)
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(28),
                  child: Column(
                    children: [
                      const Icon(Icons.videocam_off_outlined, size: 38),
                      const SizedBox(height: 10),
                      Text(
                        widget.sessionController.error ??
                            'No cameras were returned by the backend.',
                        textAlign: TextAlign.center,
                      ),
                    ],
                  ),
                ),
              )
            else
              LayoutBuilder(
                builder: (context, constraints) {
                  final columns = constraints.maxWidth >= 1100
                      ? 4
                      : constraints.maxWidth >= 720
                          ? 3
                          : constraints.maxWidth >= 480
                              ? 2
                              : 1;
                  return GridView.builder(
                    shrinkWrap: true,
                    physics: const NeverScrollableScrollPhysics(),
                    itemCount: visible.length,
                    gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(
                      crossAxisCount: columns,
                      crossAxisSpacing: 12,
                      mainAxisSpacing: 12,
                      childAspectRatio: 1.16,
                    ),
                    itemBuilder: (context, index) => CameraCard(
                      camera: visible[index],
                      onTap: () => _showCamera(context, visible[index]),
                    ),
                  );
                },
              ),
            const SizedBox(height: 24),
          ],
        ),
      ),
    );
  }

  void _showCamera(BuildContext context, CameraInfo camera) {
    showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      showDragHandle: true,
      builder: (context) {
        return SafeArea(
          child: Padding(
            padding: const EdgeInsets.fromLTRB(20, 0, 20, 24),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Text(
                  camera.name,
                  style: Theme.of(
                    context,
                  ).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w800),
                ),
                const SizedBox(height: 14),
                AspectRatio(
                  aspectRatio: 16 / 9,
                  child: CameraCard(camera: camera),
                ),
                const SizedBox(height: 14),
                Row(
                  children: [
                    const StatusPill(
                      label: 'WEBRTC · 148 MS',
                      color: AppColors.green,
                    ),
                    const Spacer(),
                    IconButton.filledTonal(
                      tooltip: 'Snapshot',
                      onPressed: () {},
                      icon: const Icon(Icons.camera_alt_outlined),
                    ),
                    const SizedBox(width: 8),
                    IconButton.filledTonal(
                      tooltip: 'Fullscreen',
                      onPressed: () {},
                      icon: const Icon(Icons.fullscreen_rounded),
                    ),
                  ],
                ),
              ],
            ),
          ),
        );
      },
    );
  }
}

class AlertsScreen extends StatefulWidget {
  const AlertsScreen({super.key});

  @override
  State<AlertsScreen> createState() => _AlertsScreenState();
}

class _AlertsScreenState extends State<AlertsScreen> {
  bool active = true;

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      child: ContentFrame(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            PageHeading(
              title: 'Alerts',
              subtitle: active
                  ? '7 active alerts need attention'
                  : 'Resolved factory alerts',
            ),
            const SizedBox(height: 16),
            SegmentedButton<bool>(
              segments: const [
                ButtonSegment(
                  value: true,
                  label: Text('Active (7)'),
                  icon: Icon(Icons.notifications_active_outlined),
                ),
                ButtonSegment(
                  value: false,
                  label: Text('Resolved'),
                  icon: Icon(Icons.check_circle_outline_rounded),
                ),
              ],
              selected: {active},
              onSelectionChanged: (value) =>
                  setState(() => active = value.first),
            ),
            const SizedBox(height: 16),
            if (active)
              for (final alert in alerts) ...[
                AlertTile(alert: alert),
                const SizedBox(height: 10),
              ]
            else
              for (final alert in alerts.reversed.take(3)) ...[
                Card(
                  child: ListTile(
                    leading: const CircleAvatar(
                      backgroundColor: Color(0x2235D58D),
                      child: Icon(Icons.check_rounded, color: AppColors.green),
                    ),
                    title: Text(alert.title),
                    subtitle: Text('${alert.location} · Resolved'),
                    trailing: const Text('Today'),
                  ),
                ),
                const SizedBox(height: 10),
              ],
            const SizedBox(height: 24),
          ],
        ),
      ),
    );
  }
}

class MachinesScreen extends StatefulWidget {
  const MachinesScreen({super.key});

  @override
  State<MachinesScreen> createState() => _MachinesScreenState();
}

class _MachinesScreenState extends State<MachinesScreen> {
  String status = 'All';

  @override
  Widget build(BuildContext context) {
    final filtered = status == 'All'
        ? machines
        : machines.where((machine) => machine.status == status).toList();
    return SingleChildScrollView(
      child: ContentFrame(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const PageHeading(
              title: 'Machines',
              subtitle: '24 connected machines across 4 production lines',
            ),
            const SizedBox(height: 16),
            Wrap(
              spacing: 8,
              children: [
                for (final item in ['All', 'Running', 'Stopped'])
                  ChoiceChip(
                    label: Text(item),
                    selected: status == item,
                    onSelected: (_) => setState(() => status = item),
                  ),
              ],
            ),
            const SizedBox(height: 16),
            for (final machine in filtered) ...[
              MachineTile(machine: machine),
              const SizedBox(height: 10),
            ],
            const SizedBox(height: 24),
          ],
        ),
      ),
    );
  }
}

class AnalyticsScreen extends StatelessWidget {
  const AnalyticsScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      child: ContentFrame(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const PageHeading(
              title: 'Production Analytics',
              subtitle: 'Today · Main Factory',
            ),
            const SizedBox(height: 16),
            LayoutBuilder(
              builder: (context, constraints) {
                final wide = constraints.maxWidth >= 800;
                final production = const Card(
                  child: Padding(
                    padding: EdgeInsets.all(18),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        Text(
                          'Production',
                          style: TextStyle(fontWeight: FontWeight.w800),
                        ),
                        SizedBox(height: 15),
                        Row(
                          children: [
                            Expanded(
                              child: _DataPoint(
                                label: 'Plan',
                                value: '1,250',
                                color: AppColors.blue,
                              ),
                            ),
                            Expanded(
                              child: _DataPoint(
                                label: 'Actual',
                                value: '1,086',
                                color: AppColors.cyan,
                              ),
                            ),
                          ],
                        ),
                        SizedBox(height: 18),
                        ProductionBars(height: 190),
                      ],
                    ),
                  ),
                );
                final oee = const Card(
                  child: Padding(
                    padding: EdgeInsets.all(18),
                    child: Column(
                      children: [
                        Align(
                          alignment: Alignment.centerLeft,
                          child: Text(
                            'Overall Equipment Effectiveness',
                            style: TextStyle(fontWeight: FontWeight.w800),
                          ),
                        ),
                        SizedBox(height: 20),
                        DonutChart(
                          value: .78,
                          color: AppColors.green,
                          size: 154,
                          label: 'OEE',
                        ),
                        SizedBox(height: 20),
                        _IndicatorRow(
                          label: 'Availability',
                          value: '85%',
                          color: AppColors.green,
                        ),
                        SizedBox(height: 11),
                        _IndicatorRow(
                          label: 'Performance',
                          value: '82%',
                          color: AppColors.cyan,
                        ),
                        SizedBox(height: 11),
                        _IndicatorRow(
                          label: 'Quality',
                          value: '90%',
                          color: AppColors.purple,
                        ),
                      ],
                    ),
                  ),
                );
                if (wide) {
                  return Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Expanded(flex: 6, child: production),
                      const SizedBox(width: 14),
                      Expanded(flex: 4, child: oee),
                    ],
                  );
                }
                return Column(
                  children: [production, const SizedBox(height: 14), oee],
                );
              },
            ),
            const SizedBox(height: 14),
            const _EfficiencySummary(),
            const SizedBox(height: 24),
          ],
        ),
      ),
    );
  }
}

class _IndicatorRow extends StatelessWidget {
  const _IndicatorRow({
    required this.label,
    required this.value,
    required this.color,
  });

  final String label;
  final String value;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Container(
          width: 8,
          height: 8,
          decoration: BoxDecoration(color: color, shape: BoxShape.circle),
        ),
        const SizedBox(width: 9),
        Expanded(child: Text(label)),
        Text(value, style: const TextStyle(fontWeight: FontWeight.w800)),
      ],
    );
  }
}

class _EfficiencySummary extends StatelessWidget {
  const _EfficiencySummary();

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(18),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Shift Performance',
              style: TextStyle(fontWeight: FontWeight.w800),
            ),
            const SizedBox(height: 16),
            for (final item in [
              ('Morning shift', .93, AppColors.green),
              ('Afternoon shift', .84, AppColors.cyan),
              ('Night shift', .71, AppColors.amber),
            ]) ...[
              Row(
                children: [
                  SizedBox(width: 120, child: Text(item.$1)),
                  Expanded(
                    child: LinearProgressIndicator(
                      value: item.$2,
                      minHeight: 8,
                      borderRadius: BorderRadius.circular(8),
                      color: item.$3,
                      backgroundColor: Theme.of(
                        context,
                      ).dividerColor.withValues(alpha: .5),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Text('${(item.$2 * 100).round()}%'),
                ],
              ),
              const SizedBox(height: 14),
            ],
          ],
        ),
      ),
    );
  }
}

class ViolationsScreen extends StatelessWidget {
  const ViolationsScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      child: ContentFrame(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const PageHeading(
              title: 'Violations',
              subtitle: '23 events detected today',
            ),
            const SizedBox(height: 16),
            Card(
              child: Padding(
                padding: const EdgeInsets.all(18),
                child: LayoutBuilder(
                  builder: (context, constraints) {
                    final chart = const DonutChart(
                      value: .68,
                      color: AppColors.red,
                      size: 154,
                      label: '23 total',
                    );
                    final legend = const Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        _Legend(
                          color: AppColors.red,
                          label: 'No PPE',
                          value: '9',
                        ),
                        _Legend(
                          color: AppColors.blue,
                          label: 'No helmet',
                          value: '5',
                        ),
                        _Legend(
                          color: AppColors.amber,
                          label: 'Wrong operation',
                          value: '5',
                        ),
                        _Legend(
                          color: AppColors.purple,
                          label: 'Unauthorized access',
                          value: '4',
                        ),
                      ],
                    );
                    if (constraints.maxWidth >= 600) {
                      return Row(
                        mainAxisAlignment: MainAxisAlignment.spaceAround,
                        children: [chart, legend],
                      );
                    }
                    return Column(
                      children: [chart, const SizedBox(height: 18), legend],
                    );
                  },
                ),
              ),
            ),
            const SizedBox(height: 18),
            Text(
              'Recent Violations',
              style: Theme.of(
                context,
              ).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w800),
            ),
            const SizedBox(height: 10),
            for (final alert in alerts.take(4)) ...[
              AlertTile(alert: alert),
              const SizedBox(height: 10),
            ],
            const SizedBox(height: 24),
          ],
        ),
      ),
    );
  }
}

class _Legend extends StatelessWidget {
  const _Legend({
    required this.color,
    required this.label,
    required this.value,
  });
  final Color color;
  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 7),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 10,
            height: 10,
            decoration: BoxDecoration(color: color, shape: BoxShape.circle),
          ),
          const SizedBox(width: 9),
          SizedBox(width: 150, child: Text(label)),
          Text(value, style: const TextStyle(fontWeight: FontWeight.w900)),
        ],
      ),
    );
  }
}

class ReportsScreen extends StatelessWidget {
  const ReportsScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final items = [
      (
        'Production Report',
        'Daily production summary',
        Icons.calendar_month_outlined,
        AppColors.blue,
      ),
      (
        'Downtime Report',
        'Downtime and reasons',
        Icons.schedule_outlined,
        AppColors.purple,
      ),
      (
        'Quality Report',
        'Defects and quality',
        Icons.verified_user_outlined,
        AppColors.green,
      ),
      (
        'Shift Report',
        'Shift performance',
        Icons.groups_outlined,
        AppColors.cyan,
      ),
      (
        'Custom Report',
        'Build your own report',
        Icons.note_add_outlined,
        AppColors.amber,
      ),
    ];
    return SingleChildScrollView(
      child: ContentFrame(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            PageHeading(
              title: 'Reports',
              subtitle: 'Factory intelligence ready to export',
              trailing: IconButton.filledTonal(
                tooltip: 'Report history',
                onPressed: () {},
                icon: const Icon(Icons.history_rounded),
              ),
            ),
            const SizedBox(height: 16),
            for (final item in items) ...[
              Card(
                child: ListTile(
                  minVerticalPadding: 16,
                  leading: Container(
                    width: 46,
                    height: 46,
                    decoration: BoxDecoration(
                      color: item.$4.withValues(alpha: .13),
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Icon(item.$3, color: item.$4),
                  ),
                  title: Text(
                    item.$1,
                    style: const TextStyle(fontWeight: FontWeight.w800),
                  ),
                  subtitle: Text(item.$2),
                  trailing: const Icon(Icons.chevron_right_rounded),
                  onTap: () => _reportSheet(context, item.$1),
                ),
              ),
              const SizedBox(height: 10),
            ],
            const SizedBox(height: 24),
          ],
        ),
      ),
    );
  }

  void _reportSheet(BuildContext context, String title) {
    showModalBottomSheet<void>(
      context: context,
      showDragHandle: true,
      builder: (context) => Padding(
        padding: const EdgeInsets.fromLTRB(20, 0, 20, 28),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(
              title,
              style: Theme.of(
                context,
              ).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w800),
            ),
            const SizedBox(height: 14),
            const Text(
              'Choose a period and format. Backend export will be connected '
              'to the existing AI Vision report service.',
            ),
            const SizedBox(height: 18),
            const Row(
              children: [
                Expanded(
                  child: TextField(
                    decoration: InputDecoration(labelText: 'From'),
                  ),
                ),
                SizedBox(width: 12),
                Expanded(
                  child: TextField(
                    decoration: InputDecoration(labelText: 'To'),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 14),
            FilledButton.icon(
              onPressed: Navigator.of(context).pop,
              icon: const Icon(Icons.download_rounded),
              label: const Text('Generate report'),
            ),
          ],
        ),
      ),
    );
  }
}

class NotificationsScreen extends StatelessWidget {
  const NotificationsScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final items = [
      (
        'Alert: No Safety Helmet',
        'Line 2 · Area A',
        '2 min ago',
        Icons.notifications_active_rounded,
        AppColors.red,
      ),
      (
        'Alert Resolved',
        'Unauthorized Access at Gate',
        '10 min ago',
        Icons.check_circle_rounded,
        AppColors.green,
      ),
      (
        'Shift Started',
        'Evening shift started',
        '1 hour ago',
        Icons.badge_rounded,
        AppColors.blue,
      ),
      (
        'Report Generated',
        'Daily Production Report',
        '2 hours ago',
        Icons.description_rounded,
        AppColors.purple,
      ),
      (
        'Camera Offline',
        'Warehouse · Cam 03',
        '3 hours ago',
        Icons.videocam_off_rounded,
        AppColors.amber,
      ),
    ];
    return SingleChildScrollView(
      child: ContentFrame(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const PageHeading(
              title: 'Notifications',
              subtitle: 'System, AI, and factory activity',
            ),
            const SizedBox(height: 16),
            for (final item in items) ...[
              Card(
                child: ListTile(
                  minVerticalPadding: 13,
                  leading: Container(
                    width: 44,
                    height: 44,
                    decoration: BoxDecoration(
                      color: item.$5.withValues(alpha: .14),
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Icon(item.$4, color: item.$5),
                  ),
                  title: Text(
                    item.$1,
                    style: const TextStyle(fontWeight: FontWeight.w800),
                  ),
                  subtitle: Text(item.$2),
                  trailing: Text(item.$3, style: const TextStyle(fontSize: 10)),
                ),
              ),
              const SizedBox(height: 10),
            ],
            const SizedBox(height: 24),
          ],
        ),
      ),
    );
  }
}

class ProfileScreen extends StatelessWidget {
  const ProfileScreen({super.key, required this.role, required this.onLogout});

  final UserRole role;
  final VoidCallback onLogout;

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      child: ContentFrame(
        child: Column(
          children: [
            const SizedBox(height: 14),
            Stack(
              children: [
                const CircleAvatar(
                  radius: 56,
                  backgroundColor: AppColors.blue,
                  child: Text(
                    'OJ',
                    style: TextStyle(
                      color: Colors.white,
                      fontSize: 32,
                      fontWeight: FontWeight.w900,
                    ),
                  ),
                ),
                Positioned(
                  right: 0,
                  bottom: 0,
                  child: CircleAvatar(
                    radius: 17,
                    backgroundColor: Theme.of(context).cardColor,
                    child: const Icon(Icons.camera_alt_rounded, size: 17),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 15),
            Text(
              'Odiljon Jamoliddinov',
              style: Theme.of(
                context,
              ).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w900),
            ),
            const SizedBox(height: 4),
            Text(
              role.label,
              style: const TextStyle(
                color: AppColors.blue,
                fontWeight: FontWeight.w700,
              ),
            ),
            const Text('Main Factory'),
            const SizedBox(height: 24),
            const Card(
              child: Column(
                children: [
                  _ProfileItem(
                    icon: Icons.person_outline_rounded,
                    label: 'Personal Information',
                  ),
                  Divider(height: 1),
                  _ProfileItem(
                    icon: Icons.history_rounded,
                    label: 'My Activity',
                  ),
                  Divider(height: 1),
                  _ProfileItem(
                    icon: Icons.star_outline_rounded,
                    label: 'Favorite Cameras',
                  ),
                  Divider(height: 1),
                  _ProfileItem(
                    icon: Icons.bookmark_outline_rounded,
                    label: 'Saved Reports',
                  ),
                  Divider(height: 1),
                  _ProfileItem(
                    icon: Icons.lock_outline_rounded,
                    label: 'Change Password',
                  ),
                ],
              ),
            ),
            const SizedBox(height: 14),
            OutlinedButton.icon(
              onPressed: onLogout,
              icon: const Icon(Icons.logout_rounded, color: AppColors.red),
              label: const Text(
                'Log out',
                style: TextStyle(color: AppColors.red),
              ),
            ),
            const SizedBox(height: 24),
          ],
        ),
      ),
    );
  }
}

class _ProfileItem extends StatelessWidget {
  const _ProfileItem({required this.icon, required this.label});
  final IconData icon;
  final String label;

  @override
  Widget build(BuildContext context) {
    return ListTile(
      leading: Icon(icon),
      title: Text(label),
      trailing: const Icon(Icons.chevron_right_rounded),
      onTap: () {},
    );
  }
}

class SettingsScreen extends StatefulWidget {
  const SettingsScreen({
    super.key,
    required this.themeController,
    required this.sessionController,
  });

  final ThemeController themeController;
  final SessionController sessionController;

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  bool push = true;
  bool email = true;
  bool critical = true;
  bool biometrics = false;

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      child: ContentFrame(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const PageHeading(
              title: 'Settings',
              subtitle: 'Application, security, and notification preferences',
            ),
            const SizedBox(height: 18),
            _SettingsGroup(
              title: 'Appearance',
              children: [
                ThemeToggleButton(
                  controller: widget.themeController,
                  label: true,
                ),
                const Divider(height: 1),
                const ListTile(
                  leading: Icon(Icons.language_rounded),
                  title: Text('Language'),
                  trailing: Text('English  ›'),
                ),
                const Divider(height: 1),
                const ListTile(
                  leading: Icon(Icons.straighten_rounded),
                  title: Text('Units'),
                  trailing: Text('Metric  ›'),
                ),
              ],
            ),
            const SizedBox(height: 14),
            _SettingsGroup(
              title: 'Backend connection',
              children: [
                ListTile(
                  leading: Icon(
                    widget.sessionController.connected
                        ? Icons.cloud_done_outlined
                        : Icons.cloud_off_outlined,
                    color: widget.sessionController.connected
                        ? AppColors.green
                        : AppColors.red,
                  ),
                  title: Text(widget.sessionController.serverUrl),
                  subtitle: Text(
                    '${widget.sessionController.role.label} · '
                    '${widget.sessionController.userEmail}',
                  ),
                  trailing: IconButton(
                    tooltip: 'Refresh',
                    onPressed: widget.sessionController.busy
                        ? null
                        : widget.sessionController.refresh,
                    icon: const Icon(Icons.refresh_rounded),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 14),
            _SettingsGroup(
              title: 'Notifications',
              children: [
                SwitchListTile(
                  secondary: const Icon(Icons.notifications_outlined),
                  value: push,
                  title: const Text('Push notifications'),
                  onChanged: (value) => setState(() => push = value),
                ),
                const Divider(height: 1),
                SwitchListTile(
                  secondary: const Icon(Icons.email_outlined),
                  value: email,
                  title: const Text('Email notifications'),
                  onChanged: (value) => setState(() => email = value),
                ),
                const Divider(height: 1),
                SwitchListTile(
                  secondary: const Icon(Icons.notification_important_outlined),
                  value: critical,
                  title: const Text('Critical alerts'),
                  onChanged: (value) => setState(() => critical = value),
                ),
              ],
            ),
            const SizedBox(height: 14),
            _SettingsGroup(
              title: 'Security',
              children: [
                SwitchListTile(
                  secondary: const Icon(Icons.fingerprint_rounded),
                  value: biometrics,
                  title: const Text('Biometric authentication'),
                  onChanged: (value) => setState(() => biometrics = value),
                ),
                const Divider(height: 1),
                const ListTile(
                  leading: Icon(Icons.devices_outlined),
                  title: Text('Active sessions'),
                  trailing: Text('2  ›'),
                ),
              ],
            ),
            const SizedBox(height: 14),
            const _SettingsGroup(
              title: 'About',
              children: [
                ListTile(
                  leading: Icon(Icons.info_outline_rounded),
                  title: Text('About AI Vision'),
                  trailing: Text('v1.0.0  ›'),
                ),
                Divider(height: 1),
                ListTile(
                  leading: Icon(Icons.privacy_tip_outlined),
                  title: Text('Privacy Policy'),
                  trailing: Icon(Icons.chevron_right_rounded),
                ),
              ],
            ),
            const SizedBox(height: 24),
          ],
        ),
      ),
    );
  }
}

class _SettingsGroup extends StatelessWidget {
  const _SettingsGroup({required this.title, required this.children});
  final String title;
  final List<Widget> children;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Padding(
          padding: const EdgeInsets.only(left: 4, bottom: 8),
          child: Text(
            title.toUpperCase(),
            style: TextStyle(
              color: Theme.of(context).colorScheme.onSurfaceVariant,
              fontSize: 11,
              fontWeight: FontWeight.w800,
              letterSpacing: .8,
            ),
          ),
        ),
        Card(child: Column(children: children)),
      ],
    );
  }
}

class DirectoryScreen extends StatelessWidget {
  const DirectoryScreen({
    super.key,
    required this.title,
    required this.subtitle,
    required this.icon,
  });
  final String title;
  final String subtitle;
  final IconData icon;

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      child: ContentFrame(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            PageHeading(
              title: title,
              subtitle: subtitle,
              trailing: FilledButton.icon(
                onPressed: () {},
                icon: const Icon(Icons.add_rounded),
                label: const Text('Add'),
              ),
            ),
            const SizedBox(height: 16),
            for (var i = 1; i <= 6; i++) ...[
              Card(
                child: ListTile(
                  minVerticalPadding: 14,
                  leading: CircleAvatar(
                    backgroundColor: AppColors.blue.withValues(alpha: .14),
                    child: Icon(icon, color: AppColors.blue),
                  ),
                  title: Text(
                    '$title ${i.toString().padLeft(2, '0')}',
                    style: const TextStyle(fontWeight: FontWeight.w800),
                  ),
                  subtitle: const Text('Main Factory · Active'),
                  trailing: const Icon(Icons.chevron_right_rounded),
                ),
              ),
              const SizedBox(height: 10),
            ],
            const SizedBox(height: 24),
          ],
        ),
      ),
    );
  }
}
