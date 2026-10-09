import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';
import 'cloud.dart';

/// Talks to the Stock Guru API on the NAS. Read-mostly; the only write is the watchlist.
class Api {
  Api._();
  static final Api instance = Api._();

  String baseUrl = 'http://192.168.100.122:8787';
  String token = '';
  /// 'auto' = LAN when reachable, else cloud; 'lan' / 'cloud' force one.
  String mode = 'auto';
  /// Which route served the last successful request (shown in the UI).
  String lastRoute = '';

  Future<void> load() async {
    final p = await SharedPreferences.getInstance();
    baseUrl = p.getString('baseUrl') ?? baseUrl;
    token = p.getString('token') ?? '';
    mode = p.getString('mode') ?? 'auto';
  }

  Future<void> saveMode(String m) async {
    mode = m;
    final p = await SharedPreferences.getInstance();
    await p.setString('mode', m);
  }

  Future<void> save(String url, String tok) async {
    baseUrl = url.trim().replaceAll(RegExp(r'/+$'), '');
    token = tok.trim();
    final p = await SharedPreferences.getInstance();
    await p.setString('baseUrl', baseUrl);
    await p.setString('token', token);
  }

  Map<String, String> get _headers => {'X-Token': token};
  Uri _u(String path) => Uri.parse('$baseUrl$path');
  String chartUrl(String sym) => '$baseUrl/api/chart/$sym.png';

  Future<Map<String, dynamic>> _lanJson(String path, {Duration timeout = const Duration(seconds: 20)}) async {
    final r = await http.get(_u(path), headers: _headers).timeout(timeout);
    if (r.statusCode != 200) {
      throw ApiException(r.statusCode, _err(r.body));
    }
    return json.decode(r.body) as Map<String, dynamic>;
  }

  /// Route a read: LAN first with a short timeout, then the cloud (if signed in).
  Future<Map<String, dynamic>> _route(String path, Future<Map<String, dynamic>> Function() cloudCall) async {
    if (mode != 'cloud') {
      try {
        final r = await _lanJson(path, timeout: Duration(seconds: mode == 'lan' ? 20 : 4));
        lastRoute = 'LAN';
        return r;
      } catch (e) {
        if (mode == 'lan') rethrow;
        if (e is ApiException && e.code == 401) rethrow; // reachable but wrong token: say so
        if (Cloud.instance.user == null) {
          throw ApiException(0, 'NAS not reachable on this network and you are not signed in for cloud access. Sign in under Settings to use Stock Guru away from home.');
        }
      }
    }
    if (Cloud.instance.user == null) throw ApiException(0, 'Sign in under Settings to use the cloud route.');
    try {
      final r = await cloudCall();
      lastRoute = 'cloud';
      return r;
    } on CloudException catch (e) {
      throw ApiException(0, e.message);
    } catch (e) {
      final s = '$e';
      if (s.contains('permission-denied')) {
        throw ApiException(403, 'Your Google account (${Cloud.instance.email}) is not on the allow-list yet. Ask Homi to add it.');
      }
      throw ApiException(0, s);
    }
  }

  String _err(String body) {
    try {
      final m = json.decode(body);
      return (m['error'] ?? body).toString();
    } catch (_) {
      return body;
    }
  }

  final _cloud = Cloud.instance;
  Future<Map<String, dynamic>> summary() => _route('/api/summary', _cloud.summary);
  Future<Map<String, dynamic>> stock(String sym) => _route('/api/stock/$sym', () => _cloud.stock(sym));
  Future<Map<String, dynamic>> history(String sym) => _route('/api/history/$sym', () => _cloud.history(sym));
  Future<Map<String, dynamic>> symbols() => _route('/api/symbols', _cloud.symbols);
  Future<Map<String, dynamic>> scorecard() => _route('/api/scorecard', _cloud.scorecard);
  Future<Map<String, dynamic>> status() => _route('/api/status', _cloud.requestStatus);
  Future<Map<String, dynamic>> watchlist() => _route('/api/watchlist', _cloud.watchlist);

  Future<Map<String, dynamic>> putWatchlist(List<String> symbols) async {
    if (lastRoute == 'cloud' || mode == 'cloud') {
      return _cloud.requestWatchlist(symbols);
    }
    final r = await http
        .put(_u('/api/watchlist'), headers: {..._headers, 'Content-Type': 'application/json'}, body: json.encode({'symbols': symbols}))
        .timeout(const Duration(seconds: 20));
    final body = json.decode(r.body) as Map<String, dynamic>;
    if (r.statusCode >= 300) throw ApiException(r.statusCode, body['error']?.toString() ?? r.body);
    return body;
  }
}

class ApiException implements Exception {
  final int code;
  final String message;
  ApiException(this.code, this.message);
  @override
  String toString() => 'HTTP $code: $message';
}

/// Small formatting helpers shared by the screens.
String fmtNum(dynamic v, {int d = 2}) {
  if (v == null) return 'n/a';
  final n = (v as num).toDouble();
  final s = n.toStringAsFixed(d);
  final parts = s.split('.');
  final re = RegExp(r'(\d)(?=(\d{3})+(?!\d))');
  final whole = parts[0].replaceAllMapped(re, (m) => '${m[1]},');
  return parts.length > 1 ? '$whole.${parts[1]}' : whole;
}

String fmtPct(dynamic v, {int d = 2, bool sign = true}) {
  if (v == null) return 'n/a';
  final n = (v as num).toDouble();
  return '${sign && n > 0 ? '+' : ''}${n.toStringAsFixed(d)}%';
}
