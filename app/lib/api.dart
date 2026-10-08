import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

/// Talks to the Stock Guru API on the NAS. Read-mostly; the only write is the watchlist.
class Api {
  Api._();
  static final Api instance = Api._();

  String baseUrl = 'http://192.168.100.122:8787';
  String token = '';

  Future<void> load() async {
    final p = await SharedPreferences.getInstance();
    baseUrl = p.getString('baseUrl') ?? baseUrl;
    token = p.getString('token') ?? '';
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

  Future<Map<String, dynamic>> _getJson(String path) async {
    final r = await http.get(_u(path), headers: _headers).timeout(const Duration(seconds: 20));
    if (r.statusCode != 200) {
      throw ApiException(r.statusCode, _err(r.body));
    }
    return json.decode(r.body) as Map<String, dynamic>;
  }

  String _err(String body) {
    try {
      final m = json.decode(body);
      return (m['error'] ?? body).toString();
    } catch (_) {
      return body;
    }
  }

  Future<Map<String, dynamic>> summary() => _getJson('/api/summary');
  Future<Map<String, dynamic>> stock(String sym) => _getJson('/api/stock/$sym');
  Future<Map<String, dynamic>> history(String sym) => _getJson('/api/history/$sym');
  Future<Map<String, dynamic>> symbols() => _getJson('/api/symbols');
  Future<Map<String, dynamic>> scorecard() => _getJson('/api/scorecard');
  Future<Map<String, dynamic>> status() => _getJson('/api/status');
  Future<Map<String, dynamic>> watchlist() => _getJson('/api/watchlist');

  Future<Map<String, dynamic>> putWatchlist(List<String> symbols) async {
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
