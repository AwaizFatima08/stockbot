import 'package:flutter/material.dart';
import '../api.dart';
import '../cloud.dart';
import '../widgets/common.dart';

class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key});
  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  late final TextEditingController _url = TextEditingController(text: Api.instance.baseUrl);
  late final TextEditingController _tok = TextEditingController(text: Api.instance.token);
  String _msg = '';
  String _cloudMsg = '';
  bool _busy = false;

  Future<void> _signIn() async {
    setState(() { _busy = true; _cloudMsg = ''; });
    final err = await Cloud.instance.signIn();
    if (err == null) {
      final ok = await Cloud.instance.isAllowed();
      _cloudMsg = ok ? 'Signed in as ${Cloud.instance.email}. Cloud access allowed.' : 'Signed in as ${Cloud.instance.email}, but this account is not on the allow-list yet.';
    } else {
      _cloudMsg = err;
    }
    if (mounted) setState(() => _busy = false);
  }

  Future<void> _signOut() async {
    await Cloud.instance.signOut();
    setState(() => _cloudMsg = 'Signed out.');
  }

  Future<void> _test() async {
    await Api.instance.save(_url.text, _tok.text);
    try {
      final s = await Api.instance.summary();
      setState(() => _msg = 'Connected. Data as of ${s['as_of']}.');
    } catch (e) {
      setState(() => _msg = 'Failed: $e');
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Settings')),
      body: ListView(padding: const EdgeInsets.all(16), children: [
        TextField(controller: _url, decoration: const InputDecoration(labelText: 'Server address', hintText: 'http://192.168.100.122:8787', border: OutlineInputBorder()), keyboardType: TextInputType.url),
        const SizedBox(height: 12),
        TextField(controller: _tok, decoration: const InputDecoration(labelText: 'API token (STOCKBOT_API_TOKEN from secrets.env on the NAS)', border: OutlineInputBorder()), obscureText: true),
        const SizedBox(height: 12),
        FilledButton(onPressed: _test, child: const Text('Save and test connection')),
        const SizedBox(height: 8),
        Text(_msg),
        const SizedBox(height: 24),
        const Text('Away from home (cloud)', style: TextStyle(fontWeight: FontWeight.w700)),
        const SizedBox(height: 6),
        const Text('Sign in with the Google account Homi has allowed. The app then reads the analysis from the cloud whenever the NAS is not reachable.', style: TextStyle(fontSize: 13)),
        const SizedBox(height: 8),
        if (Cloud.instance.user == null)
          FilledButton.tonalIcon(onPressed: _busy ? null : _signIn, icon: const Icon(Icons.login), label: Text(_busy ? 'Signing in...' : 'Sign in with Google'))
        else
          Row(children: [
            Expanded(child: Text('Signed in: ${Cloud.instance.email}')),
            TextButton(onPressed: _signOut, child: const Text('Sign out')),
          ]),
        if (Cloud.instance.initError != null) Text('Firebase: ${Cloud.instance.initError}', style: const TextStyle(color: Colors.orange, fontSize: 12)),
        if (_cloudMsg.isNotEmpty) Padding(padding: const EdgeInsets.only(top: 4), child: Text(_cloudMsg)),
        const SizedBox(height: 12),
        const Text('Data route', style: TextStyle(fontWeight: FontWeight.w600)),
        SegmentedButton<String>(
          segments: const [ButtonSegment(value: 'auto', label: Text('Auto')), ButtonSegment(value: 'lan', label: Text('Home only')), ButtonSegment(value: 'cloud', label: Text('Cloud only'))],
          selected: {Api.instance.mode},
          onSelectionChanged: (v) async { await Api.instance.saveMode(v.first); setState(() {}); },
        ),
        Text('Auto tries the NAS first, then the cloud. Last used: ${Api.instance.lastRoute.isEmpty ? 'none yet' : Api.instance.lastRoute}.', style: const TextStyle(fontSize: 12)),
        const SizedBox(height: 24),
        const Text('About', style: TextStyle(fontWeight: FontWeight.w700)),
        const SizedBox(height: 6),
        const Text('Stock Guru reads the analysis produced nightly on the home NAS from official PSX end-of-day data. '
            'It describes data, statistics and history. It never gives buy/sell advice, never predicts prices and never places orders.'),
        const SizedBox(height: 12),
        const Text(kDisclaimer, style: TextStyle(fontSize: 11)),
      ]),
    );
  }
}
