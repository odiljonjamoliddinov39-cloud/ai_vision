import 'package:flutter/material.dart';

import 'data.dart';
import 'screens.dart';
import 'theme.dart';
import 'widgets.dart';

enum AppSection {
  dashboard('Dashboard', Icons.home_outlined, Icons.home_rounded),
  cameras('Live Cameras', Icons.videocam_outlined, Icons.videocam_rounded),
  machines(
    'Machines',
    Icons.precision_manufacturing_outlined,
    Icons.precision_manufacturing_rounded,
  ),
  alerts(
    'Alerts',
    Icons.notifications_none_rounded,
    Icons.notifications_rounded,
  ),
  analytics('Analytics', Icons.insights_outlined, Icons.insights_rounded),
  violations('Violations', Icons.gpp_bad_outlined, Icons.gpp_bad_rounded),
  reports(
    'Reports',
    Icons.insert_chart_outlined_rounded,
    Icons.insert_chart_rounded,
  ),
  notifications(
    'Notifications',
    Icons.mark_email_unread_outlined,
    Icons.mark_email_unread_rounded,
  ),
  workers('Workers', Icons.groups_outlined, Icons.groups_rounded),
  documents('Documents', Icons.folder_copy_outlined, Icons.folder_copy_rounded),
  settings('Settings', Icons.settings_outlined, Icons.settings_rounded),
  profile('Profile', Icons.person_outline_rounded, Icons.person_rounded);

  const AppSection(this.label, this.icon, this.selectedIcon);
  final String label;
  final IconData icon;
  final IconData selectedIcon;
}

class AppShell extends StatefulWidget {
  const AppShell({
    super.key,
    required this.themeController,
    required this.sessionController,
    required this.onLogout,
  });

  final ThemeController themeController;
  final SessionController sessionController;
  final VoidCallback onLogout;

  @override
  State<AppShell> createState() => _AppShellState();
}

class _AppShellState extends State<AppShell> {
  AppSection section = AppSection.dashboard;
  final scaffoldKey = GlobalKey<ScaffoldState>();

  static const primarySections = [
    AppSection.dashboard,
    AppSection.cameras,
    AppSection.alerts,
    AppSection.reports,
  ];

  void navigate(AppSection value) {
    setState(() => section = value);
    if (scaffoldKey.currentState?.isDrawerOpen ?? false) {
      scaffoldKey.currentState?.closeDrawer();
    }
  }

  Widget page() => switch (section) {
        AppSection.dashboard => DashboardScreen(
            onNavigate: navigate,
            sessionController: widget.sessionController,
          ),
        AppSection.cameras => CamerasScreen(
            sessionController: widget.sessionController,
          ),
        AppSection.machines => const MachinesScreen(),
        AppSection.alerts => const AlertsScreen(),
        AppSection.analytics => const AnalyticsScreen(),
        AppSection.violations => const ViolationsScreen(),
        AppSection.reports => const ReportsScreen(),
        AppSection.notifications => const NotificationsScreen(),
        AppSection.workers => const DirectoryScreen(
            title: 'Workers',
            subtitle: 'Shift assignments and workforce status',
            icon: Icons.groups_rounded,
          ),
        AppSection.documents => const DirectoryScreen(
            title: 'Documents',
            subtitle: 'Factory policies, inspection files and certificates',
            icon: Icons.folder_copy_rounded,
          ),
        AppSection.settings => SettingsScreen(
            themeController: widget.themeController,
            sessionController: widget.sessionController,
          ),
        AppSection.profile => ProfileScreen(
            role: widget.sessionController.role,
            onLogout: widget.onLogout,
          ),
      };

  int get bottomIndex {
    final index = primarySections.indexOf(section);
    return index >= 0 ? index : 4;
  }

  @override
  Widget build(BuildContext context) {
    final width = MediaQuery.sizeOf(context).width;
    final desktop = width >= 1050;

    return ListenableBuilder(
      listenable: widget.sessionController,
      builder: (context, _) {
        return Scaffold(
          key: scaffoldKey,
          appBar: AppBar(
            leading: desktop
                ? null
                : Builder(
                    builder: (context) => IconButton(
                      tooltip: 'Menu',
                      onPressed: Scaffold.of(context).openDrawer,
                      icon: const Icon(Icons.menu_rounded),
                    ),
                  ),
            automaticallyImplyLeading: !desktop,
            title: Text(section.label),
            actions: [
              if (!widget.sessionController.connected)
                const Padding(
                  padding: EdgeInsets.symmetric(horizontal: 6),
                  child: Tooltip(
                    message: 'Backend connection is unavailable',
                    child: Icon(
                      Icons.cloud_off_outlined,
                      color: AppColors.amber,
                    ),
                  ),
                ),
              IconButton(
                tooltip: 'Refresh backend data',
                onPressed: widget.sessionController.busy
                    ? null
                    : widget.sessionController.refresh,
                icon: widget.sessionController.busy
                    ? const SizedBox.square(
                        dimension: 18,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Icon(Icons.refresh_rounded),
              ),
              IconButton(
                tooltip: 'Search',
                onPressed: () {},
                icon: const Icon(Icons.search_rounded),
              ),
              Badge(
                label: const Text('7'),
                backgroundColor: AppColors.red,
                offset: const Offset(-4, 3),
                child: IconButton(
                  tooltip: 'Notifications',
                  onPressed: () => navigate(AppSection.notifications),
                  icon: const Icon(Icons.notifications_none_rounded),
                ),
              ),
              const SizedBox(width: 4),
              ThemeToggleButton(controller: widget.themeController),
              const SizedBox(width: 10),
            ],
          ),
          drawer: desktop
              ? null
              : _AppDrawer(
                  section: section,
                  role: widget.sessionController.role,
                  userName: widget.sessionController.userName,
                  themeController: widget.themeController,
                  onNavigate: navigate,
                  onLogout: widget.onLogout,
                ),
          body: desktop
              ? Row(
                  children: [
                    _DesktopRail(
                      section: section,
                      role: widget.sessionController.role,
                      onNavigate: navigate,
                      onLogout: widget.onLogout,
                    ),
                    const VerticalDivider(width: 1),
                    Expanded(
                      child: AnimatedSwitcher(
                        duration: const Duration(milliseconds: 220),
                        child: KeyedSubtree(
                          key: ValueKey(section),
                          child: page(),
                        ),
                      ),
                    ),
                  ],
                )
              : AnimatedSwitcher(
                  duration: const Duration(milliseconds: 220),
                  child: KeyedSubtree(key: ValueKey(section), child: page()),
                ),
          bottomNavigationBar: desktop
              ? null
              : NavigationBar(
                  selectedIndex: bottomIndex,
                  onDestinationSelected: (index) {
                    if (index < primarySections.length) {
                      navigate(primarySections[index]);
                    } else {
                      scaffoldKey.currentState?.openDrawer();
                    }
                  },
                  destinations: const [
                    NavigationDestination(
                      icon: Icon(Icons.home_outlined),
                      selectedIcon: Icon(Icons.home_rounded),
                      label: 'Home',
                    ),
                    NavigationDestination(
                      icon: Icon(Icons.videocam_outlined),
                      selectedIcon: Icon(Icons.videocam_rounded),
                      label: 'Cameras',
                    ),
                    NavigationDestination(
                      icon: Badge(
                        label: Text('7'),
                        child: Icon(Icons.notifications_none_rounded),
                      ),
                      selectedIcon: Icon(Icons.notifications_rounded),
                      label: 'Alerts',
                    ),
                    NavigationDestination(
                      icon: Icon(Icons.insert_chart_outlined_rounded),
                      selectedIcon: Icon(Icons.insert_chart_rounded),
                      label: 'Reports',
                    ),
                    NavigationDestination(
                      icon: Icon(Icons.menu_rounded),
                      label: 'More',
                    ),
                  ],
                ),
        );
      },
    );
  }
}

class _AppDrawer extends StatelessWidget {
  const _AppDrawer({
    required this.section,
    required this.role,
    required this.userName,
    required this.themeController,
    required this.onNavigate,
    required this.onLogout,
  });

  final AppSection section;
  final UserRole role;
  final String userName;
  final ThemeController themeController;
  final ValueChanged<AppSection> onNavigate;
  final VoidCallback onLogout;

  @override
  Widget build(BuildContext context) {
    return Drawer(
      child: SafeArea(
        child: Column(
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(18, 16, 18, 12),
              child: Row(
                children: [
                  const Expanded(child: AiVisionLogo(size: 38)),
                  IconButton(
                    onPressed: Navigator.of(context).pop,
                    icon: const Icon(Icons.close_rounded),
                  ),
                ],
              ),
            ),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 14),
              child: Card(
                child: ListTile(
                  leading: const CircleAvatar(
                    backgroundColor: AppColors.blue,
                    child: Text(
                      'OJ',
                      style: TextStyle(
                        color: Colors.white,
                        fontWeight: FontWeight.w800,
                      ),
                    ),
                  ),
                  title: Text(
                    userName,
                    style: const TextStyle(
                      fontWeight: FontWeight.w800,
                      fontSize: 13,
                    ),
                  ),
                  subtitle: Text(role.label),
                  trailing: const Icon(Icons.unfold_more_rounded, size: 18),
                ),
              ),
            ),
            const SizedBox(height: 8),
            Expanded(
              child: ListView(
                padding: const EdgeInsets.symmetric(horizontal: 10),
                children: [
                  for (final item in _visibleSections(role))
                    ListTile(
                      selected: item == section,
                      selectedColor: AppColors.blue,
                      selectedTileColor: AppColors.blue.withValues(alpha: .12),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(9),
                      ),
                      leading: Icon(
                        item == section ? item.selectedIcon : item.icon,
                        size: 21,
                      ),
                      title: Text(
                        item.label,
                        style: const TextStyle(
                          fontSize: 13,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                      onTap: () => onNavigate(item),
                    ),
                  const Divider(height: 24),
                  ThemeToggleButton(controller: themeController, label: true),
                ],
              ),
            ),
            const Divider(height: 1),
            ListTile(
              leading: const Icon(Icons.logout_rounded, color: AppColors.red),
              title: const Text(
                'Log out',
                style: TextStyle(
                  color: AppColors.red,
                  fontWeight: FontWeight.w700,
                ),
              ),
              onTap: onLogout,
            ),
          ],
        ),
      ),
    );
  }
}

class _DesktopRail extends StatelessWidget {
  const _DesktopRail({
    required this.section,
    required this.role,
    required this.onNavigate,
    required this.onLogout,
  });

  final AppSection section;
  final UserRole role;
  final ValueChanged<AppSection> onNavigate;
  final VoidCallback onLogout;

  @override
  Widget build(BuildContext context) {
    final items = _visibleSections(role);
    final selected = items.indexOf(section);
    return NavigationRail(
      extended: MediaQuery.sizeOf(context).width >= 1300,
      selectedIndex: selected < 0 ? 0 : selected,
      onDestinationSelected: (index) => onNavigate(items[index]),
      leading: const Padding(
        padding: EdgeInsets.only(bottom: 20),
        child: AiVisionLogo(size: 36, showText: false),
      ),
      trailing: Expanded(
        child: Align(
          alignment: Alignment.bottomCenter,
          child: Padding(
            padding: const EdgeInsets.only(bottom: 14),
            child: IconButton(
              tooltip: 'Log out',
              onPressed: onLogout,
              color: AppColors.red,
              icon: const Icon(Icons.logout_rounded),
            ),
          ),
        ),
      ),
      destinations: [
        for (final item in items)
          NavigationRailDestination(
            icon: Icon(item.icon),
            selectedIcon: Icon(item.selectedIcon),
            label: Text(item.label),
          ),
      ],
    );
  }
}

List<AppSection> _visibleSections(UserRole role) {
  return switch (role) {
    UserRole.headAdmin => AppSection.values,
    UserRole.factoryAdmin =>
      AppSection.values.where((item) => item != AppSection.documents).toList(),
    UserRole.operator => [
        AppSection.dashboard,
        AppSection.cameras,
        AppSection.machines,
        AppSection.alerts,
        AppSection.analytics,
        AppSection.notifications,
        AppSection.settings,
        AppSection.profile,
      ],
  };
}
