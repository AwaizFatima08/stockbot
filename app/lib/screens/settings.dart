import 'package:flutter/material.dart';
import '../api.dart';
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
