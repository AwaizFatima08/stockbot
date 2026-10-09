import 'dart:async';
import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:firebase_auth/firebase_auth.dart';
import 'package:firebase_core/firebase_core.dart';
import 'package:google_sign_in/google_sign_in.dart';
import 'firebase_options.dart';

/// Cloud carrier: Firestore documents published by the NAS engine, readable by
/// allowed Google accounts from anywhere. Mirrors the LAN API's shapes.
class Cloud {
  Cloud._();
  static final Cloud instance = Cloud._();
  bool _ready = false;
  String? initError;

  Future<void> init() async {
    if (_ready) return;
    try {
      await Firebase.initializeApp(options: DefaultFirebaseOptions.currentPlatform);
      await GoogleSignIn.instance.initialize();
      _ready = true;
    } catch (e) {
      initError = '$e';
    }
  }

  bool get ready => _ready;
  User? get user => _ready ? FirebaseAuth.instance.currentUser : null;
  String? get email => user?.email?.toLowerCase();
  Stream<User?> get authChanges => _ready ? FirebaseAuth.instance.authStateChanges() : const Stream.empty();

  Future<String?> signIn() async {
    if (!_ready) return initError ?? 'Firebase not initialised';
    try {
      final account = await GoogleSignIn.instance.authenticate();
      final idToken = account.authentication.idToken;
      if (idToken == null) return 'Google returned no ID token';
      final cred = GoogleAuthProvider.credential(idToken: idToken);
      await FirebaseAuth.instance.signInWithCredential(cred);
      return null;
    } on GoogleSignInException catch (e) {
      return e.code == GoogleSignInExceptionCode.canceled ? 'Sign-in cancelled' : 'Google sign-in failed: ${e.code} ${e.description ?? ''}';
    } catch (e) {
      return 'Sign-in failed: $e';
    }
  }

  Future<void> signOut() async {
    if (!_ready) return;
    try {
      await GoogleSignIn.instance.signOut();
    } catch (_) {}
    await FirebaseAuth.instance.signOut();
  }

  /// True when the signed-in email is on the engine's allow-list.
  Future<bool> isAllowed() async {
    final e = email;
    if (e == null) return false;
    try {
      final d = await FirebaseFirestore.instance.collection('allowed_users').doc(e).get();
      return d.exists;
    } catch (_) {
      return false;
    }
  }

  FirebaseFirestore get _db => FirebaseFirestore.instance;

  Future<Map<String, dynamic>> _doc(String coll, String id) async {
    final d = await _db.collection(coll).doc(id).get().timeout(const Duration(seconds: 25));
    if (!d.exists) throw CloudException('No "$coll/$id" in the cloud yet (the NAS has not published).');
    return d.data()!;
  }

  Future<Map<String, dynamic>> summary() => _doc('app', 'summary');
  Future<Map<String, dynamic>> symbols() => _doc('app', 'symbols');
  Future<Map<String, dynamic>> scorecard() => _doc('app', 'scorecard');
  Future<Map<String, dynamic>> stock(String sym) => _doc('stocks', sym.toUpperCase());
  Future<Map<String, dynamic>> history(String sym) => _doc('history', sym.toUpperCase());

  Future<Map<String, dynamic>> watchlist() async {
    final s = await summary();
    return {'symbols': (s['watchlist'] as List).map((w) => w['symbol'] as String).toList()};
  }

  Future<Map<String, dynamic>> requestWatchlist(List<String> symbols) async {
    final e = email;
    if (e == null) throw CloudException('Sign in first');
    await _db.collection('requests').doc('watchlist').set({
      'symbols': symbols,
      'status': 'pending',
      'requested_by': e,
      'requested_at': DateTime.now().toUtc().toIso8601String(),
      'message': '',
    });
    return {'message': 'Request sent. The NAS checks every 5 minutes, then regenerates (allow about 7 minutes).'};
  }

  Future<Map<String, dynamic>> requestStatus() async {
    final d = await _db.collection('requests').doc('watchlist').get();
    final m = d.data() ?? {};
    return {'busy': m['status'] == 'pending' || m['status'] == 'working', 'last_job': m};
  }
}

class CloudException implements Exception {
  final String message;
  CloudException(this.message);
  @override
  String toString() => message;
}
