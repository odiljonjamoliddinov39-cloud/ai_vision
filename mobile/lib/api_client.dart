import 'dart:async';
import 'dart:convert';
import 'dart:io';

const defaultApiBaseUrl = String.fromEnvironment(
  'AI_VISION_API_BASE_URL',
  defaultValue: 'https://67-205-160-8.sslip.io',
);

class ApiException implements Exception {
  const ApiException(this.message, {this.statusCode});

  final String message;
  final int? statusCode;

  @override
  String toString() => message;
}

class AiVisionApiClient {
  AiVisionApiClient({String baseUrl = defaultApiBaseUrl})
      : _baseUrl = _normalizeBaseUrl(baseUrl);

  final HttpClient _httpClient = HttpClient()
    ..connectionTimeout = const Duration(seconds: 12);

  String _baseUrl;
  String? token;

  String get baseUrl => _baseUrl;

  Map<String, String> get authorizationHeaders => {
        if (token != null && token!.isNotEmpty)
          HttpHeaders.authorizationHeader: 'Bearer $token',
      };

  void configure(String baseUrl) {
    _baseUrl = _normalizeBaseUrl(baseUrl);
  }

  Future<Map<String, dynamic>> login(String email, String password) {
    return postJson(
      '/api/v2/auth/login',
      body: {'email': email.trim(), 'password': password},
      authenticated: false,
    );
  }

  Future<Map<String, dynamic>> dashboard() => getJson('/api/v2/me/dashboard');

  Future<Map<String, dynamic>> status() =>
      getJson('/api/status', authenticated: false);

  Future<Map<String, dynamic>> cameras() => getJson('/api/cameras');

  Future<Map<String, dynamic>> streamHealth() =>
      getJson('/api/v2/streams/health');

  Uri snapshotUri(int slotNumber, {int? cacheKey}) {
    return Uri.parse(_baseUrl).replace(
      path: '/api/live_frame',
      queryParameters: {
        'slot': '$slotNumber',
        't': '${cacheKey ?? DateTime.now().millisecondsSinceEpoch}',
      },
    );
  }

  Future<Map<String, dynamic>> getJson(
    String path, {
    bool authenticated = true,
  }) {
    return _requestJson('GET', path, authenticated: authenticated);
  }

  Future<Map<String, dynamic>> postJson(
    String path, {
    required Map<String, dynamic> body,
    bool authenticated = true,
  }) {
    return _requestJson(
      'POST',
      path,
      body: body,
      authenticated: authenticated,
    );
  }

  Future<Map<String, dynamic>> _requestJson(
    String method,
    String path, {
    Map<String, dynamic>? body,
    required bool authenticated,
  }) async {
    final uri = Uri.parse(_baseUrl).resolve(path);
    HttpClientRequest request;
    try {
      request = await _httpClient.openUrl(method, uri);
      request.headers.set(HttpHeaders.acceptHeader, 'application/json');
      if (authenticated && token != null && token!.isNotEmpty) {
        request.headers.set(
          HttpHeaders.authorizationHeader,
          'Bearer $token',
        );
      }
      if (body != null) {
        request.headers.contentType = ContentType.json;
        request.write(jsonEncode(body));
      }
      final response = await request.close().timeout(
            const Duration(seconds: 20),
          );
      final responseBody = await utf8.decoder.bind(response).join();
      final decoded =
          responseBody.isEmpty ? <String, dynamic>{} : jsonDecode(responseBody);
      final payload = decoded is Map<String, dynamic>
          ? decoded
          : <String, dynamic>{'data': decoded};
      if (response.statusCode < 200 || response.statusCode >= 300) {
        throw ApiException(
          _errorMessage(payload, response.statusCode),
          statusCode: response.statusCode,
        );
      }
      return payload;
    } on ApiException {
      rethrow;
    } on SocketException {
      throw ApiException(
        'Cannot reach AI Vision at $_baseUrl. Check the server address and '
        'your network connection.',
      );
    } on HandshakeException {
      throw const ApiException(
        'The server TLS certificate could not be verified.',
      );
    } on FormatException {
      throw const ApiException('The server returned an invalid response.');
    } on TimeoutException {
      throw const ApiException('The server did not respond in time.');
    }
  }

  static String _errorMessage(
    Map<String, dynamic> payload,
    int statusCode,
  ) {
    final detail = payload['detail'];
    if (detail is String && detail.isNotEmpty) {
      return detail;
    }
    return 'AI Vision request failed (HTTP $statusCode).';
  }

  static String _normalizeBaseUrl(String value) {
    var normalized = value.trim();
    if (normalized.isEmpty) {
      normalized = defaultApiBaseUrl;
    }
    if (!normalized.startsWith('http://') &&
        !normalized.startsWith('https://')) {
      normalized = 'https://$normalized';
    }
    while (normalized.endsWith('/')) {
      normalized = normalized.substring(0, normalized.length - 1);
    }
    return normalized;
  }

  void close() {
    _httpClient.close(force: true);
  }
}
