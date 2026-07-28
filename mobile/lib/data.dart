import 'dart:async';

import 'package:flutter/material.dart';

import 'api_client.dart';

enum UserRole {
  headAdmin('Head Admin'),
  factoryAdmin('Factory Admin'),
  operator('Operator');

  const UserRole(this.label);
  final String label;
}

class SessionController extends ChangeNotifier {
  SessionController({AiVisionApiClient? apiClient})
      : apiClient = apiClient ?? AiVisionApiClient();

  final AiVisionApiClient apiClient;
  UserRole _role = UserRole.factoryAdmin;
  UserRole get role => _role;

  bool busy = false;
  bool connected = false;
  String? error;
  String userName = 'AI Vision User';
  String userEmail = '';
  List<Map<String, dynamic>> modules = const [];
  Map<String, dynamic> serverStatus = const {};
  List<CameraInfo> liveCameras = const [];
  Timer? _refreshTimer;

  String get serverUrl => apiClient.baseUrl;
  bool get authenticated =>
      apiClient.token != null && apiClient.token!.isNotEmpty;

  void setRole(UserRole value) {
    _role = value;
    notifyListeners();
  }

  Future<void> login({
    required String server,
    required String email,
    required String password,
  }) async {
    busy = true;
    error = null;
    apiClient.configure(server);
    notifyListeners();

    try {
      final response = await apiClient.login(email, password);
      if (response['requires_passkey'] == true) {
        throw const ApiException(
          'This account requires its registered passkey. Use a '
          'password-enabled mobile account for this build.',
        );
      }
      final token = response['token']?.toString();
      if (token == null || token.isEmpty) {
        throw const ApiException('The server did not return a session token.');
      }
      apiClient.token = token;
      _applyIdentity(response);
      await refresh();
      _refreshTimer?.cancel();
      _refreshTimer = Timer.periodic(
        const Duration(seconds: 10),
        (_) => refresh(silent: true),
      );
    } catch (exception) {
      apiClient.token = null;
      connected = false;
      error = exception.toString();
      rethrow;
    } finally {
      busy = false;
      notifyListeners();
    }
  }

  Future<void> refresh({bool silent = false}) async {
    if (!authenticated) return;
    if (!silent) {
      busy = true;
      notifyListeners();
    }
    try {
      final results = await Future.wait([
        apiClient.dashboard(),
        apiClient.status(),
        apiClient.cameras(),
      ]);
      _applyIdentity(results[0]);
      serverStatus = results[1];
      final rows = (results[2]['cameras'] as List<dynamic>? ?? const [])
          .whereType<Map>()
          .map((item) => Map<String, dynamic>.from(item))
          .map(
            (item) => CameraInfo.fromApi(
              item,
              apiClient: apiClient,
            ),
          )
          .toList(growable: false);
      liveCameras = rows;
      connected = true;
      error = null;
    } catch (exception) {
      connected = false;
      error = exception.toString();
      if (!silent) rethrow;
    } finally {
      if (!silent) {
        busy = false;
      }
      notifyListeners();
    }
  }

  void _applyIdentity(Map<String, dynamic> payload) {
    final user = payload['user'];
    if (user is Map) {
      userName = user['name']?.toString() ?? userName;
      userEmail = user['email']?.toString() ?? userEmail;
      final roleText = [
        user['role'],
        user['role_code'],
        if (user['roles'] is List)
          ...(user['roles'] as List).map((item) => item.toString()),
      ].whereType<Object>().join(' ').toLowerCase();
      if (roleText.contains('head') || roleText.contains('super')) {
        _role = UserRole.headAdmin;
      } else if (roleText.contains('operator') || roleText.contains('viewer')) {
        _role = UserRole.operator;
      } else {
        _role = UserRole.factoryAdmin;
      }
    }
    modules = (payload['modules'] as List<dynamic>? ?? const [])
        .whereType<Map>()
        .map((item) => Map<String, dynamic>.from(item))
        .toList(growable: false);
  }

  int get onlineCameraCount =>
      liveCameras.where((camera) => camera.online).length;

  int get detectionCount {
    final health = serverStatus['health'];
    if (health is Map) {
      return _asInt(health['last_detection_count']);
    }
    return 0;
  }

  int get trackedCount {
    final health = serverStatus['health'];
    if (health is Map) {
      return _asInt(health['last_tracked_count']);
    }
    return 0;
  }

  int get framesRead {
    final health = serverStatus['health'];
    if (health is Map) {
      return _asInt(health['frames_read']);
    }
    return 0;
  }

  void logout() {
    _refreshTimer?.cancel();
    apiClient.token = null;
    busy = false;
    connected = false;
    error = null;
    userName = 'AI Vision User';
    userEmail = '';
    modules = const [];
    serverStatus = const {};
    liveCameras = const [];
    notifyListeners();
  }

  static int _asInt(Object? value) {
    if (value is int) return value;
    if (value is num) return value.round();
    return int.tryParse(value?.toString() ?? '') ?? 0;
  }

  @override
  void dispose() {
    _refreshTimer?.cancel();
    apiClient.close();
    super.dispose();
  }
}

class CameraInfo {
  const CameraInfo(
    this.name,
    this.location,
    this.channel, {
    this.id,
    this.slotNumber,
    this.snapshotUrl,
    this.snapshotHeaders = const {},
    this.online = true,
    this.highlight = false,
  });

  factory CameraInfo.fromApi(
    Map<String, dynamic> data, {
    required AiVisionApiClient apiClient,
  }) {
    final slot = SessionController._asInt(data['slot_number']);
    final status = data['status']?.toString().toLowerCase() ?? 'unknown';
    final active = data['is_active'] == true;
    final name = data['name']?.toString() ?? 'Camera ${data['id'] ?? ''}';
    return CameraInfo(
      name,
      data['location']?.toString() ??
          (active ? 'Active stream' : 'Registered camera'),
      slot > 0 ? slot : SessionController._asInt(data['id']),
      id: SessionController._asInt(data['id']),
      slotNumber: slot > 0 ? slot : null,
      snapshotUrl: slot > 0 ? apiClient.snapshotUri(slot).toString() : null,
      snapshotHeaders: apiClient.authorizationHeaders,
      online: active &&
          !const {'failed', 'offline', 'disconnected'}.contains(status),
    );
  }

  final String name;
  final String location;
  final int channel;
  final int? id;
  final int? slotNumber;
  final String? snapshotUrl;
  final Map<String, String> snapshotHeaders;
  final bool online;
  final bool highlight;
}

class AlertInfo {
  const AlertInfo(this.title, this.location, this.time, this.color, this.icon);

  final String title;
  final String location;
  final String time;
  final Color color;
  final IconData icon;
}

class MachineInfo {
  const MachineInfo(this.name, this.status, this.speed, this.oee, this.color);

  final String name;
  final String status;
  final int speed;
  final int oee;
  final Color color;
}

const demoCameras = <CameraInfo>[
  CameraInfo('Line 1 · Cam 01', 'Production Hall', 1),
  CameraInfo('Line 1 · Cam 02', 'Production Hall', 2),
  CameraInfo('Line 2 · Cam 01', 'Production Hall', 5, highlight: true),
  CameraInfo('Warehouse · Cam 01', 'Warehouse A', 9),
  CameraInfo('Gate · Cam 01', 'Main Gate', 14),
  CameraInfo('Packing · Cam 01', 'Packing Area', 19),
  CameraInfo('Receiving · Cam 02', 'Receiving', 20),
  CameraInfo('Loading · Cam 03', 'Loading Bay', 21, online: false),
];

const alerts = <AlertInfo>[
  AlertInfo(
    'No Safety Helmet',
    'Line 2 · Area A',
    '2 min ago',
    Color(0xFFFF5252),
    Icons.health_and_safety_outlined,
  ),
  AlertInfo(
    'Unauthorized Access',
    'Main Gate',
    '5 min ago',
    Color(0xFFFF5252),
    Icons.person_off_outlined,
  ),
  AlertInfo(
    'Wrong Operation',
    'Line 1 · Machine 3',
    '7 min ago',
    Color(0xFFFF8F3F),
    Icons.warning_amber_rounded,
  ),
  AlertInfo(
    'Person & Forklift Too Close',
    'Line 1 · Area B',
    '9 min ago',
    Color(0xFFFFC13B),
    Icons.precision_manufacturing_outlined,
  ),
  AlertInfo(
    'PPE Not Detected',
    'Packing Area',
    '12 min ago',
    Color(0xFFFF5252),
    Icons.visibility_off_outlined,
  ),
];

const machines = <MachineInfo>[
  MachineInfo('Machine 01 · Line 1', 'Running', 85, 78, Color(0xFF35D58D)),
  MachineInfo('Machine 02 · Line 1', 'Running', 90, 82, Color(0xFF35D58D)),
  MachineInfo('Machine 03 · Line 1', 'Stopped', 0, 41, Color(0xFFFF5252)),
  MachineInfo('Machine 04 · Line 2', 'Running', 75, 71, Color(0xFF35D58D)),
  MachineInfo('Machine 05 · Line 2', 'Maintenance', 0, 0, Color(0xFFFFB23F)),
];
