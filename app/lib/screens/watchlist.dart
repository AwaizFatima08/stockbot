import 'dart:async';
import 'package:flutter/material.dart';
import '../api.dart';
import '../widgets/common.dart';

class WatchlistScreen extends StatefulWidget {
  const WatchlistScreen({super.key});
  @override
  State<WatchlistScreen> createState() => _WatchlistScreenState();
}

class _WatchlistScreenState extends State<WatchlistScreen> {
  List<String> _symbols = [];
  List<Map<String, dynamic>> _all = [];
  Map<String, Map<String, dynamic>> _byName = {};
  bool _loading = true, _dirty = false, _saving = false;
  Object? _error;
  String _status = '';
  Timer? _poll;

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _poll?.cancel();
    super.dispose();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final w = await Api.instance.watchlist();
      final s = await Api.instance.symbols();
      _symbols = (w['symbols'] as List).cast<String>();
      _all = (s['symbols'] as List).cast<Map<String, dynamic>>();
      _byName = {for (final m in _all) m['symbol'] as String: m};
      _dirty = false;
    } catch (e) {
      _error = e;
    }
    if (mounted) setState(() => _loading = false);
  }

  Future<void> _replace(int index) async {
    final picked = await showSearch<String?>(context: context, delegate: _SymbolSearch(_all, exclude: _symbols));
    if (picked == null) return;
    setState(() {
      _symbols[index] = picked;
      _dirty = true;
    });
  }

  Future<void> _save() async {
    setState(() {
      _saving = true;
      _status = '';
    });
    try {
      final r = await Api.instance.putWatchlist(_symbols);
      setState(() {
        _status = r['message']?.toString() ?? 'saved';
        _dirty = false;
      });
      _poll?.cancel();
      _poll = Timer.periodic(const Duration(seconds: 10), (t) async {
        try {
          final st = await Api.instance.status();
          if (st['busy'] != true) {
            t.cancel();
            if (mounted) setState(() => _status = 'Regeneration finished. Pull to refresh on the Today tab.');
          }
        } catch (_) {}
      });
    } catch (e) {
      setState(() => _status = 'Save failed: $e');
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Watchlist (10 stocks)'), actions: [IconButton(onPressed: _load, icon: const Icon(Icons.refresh))]),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
              ? ErrorBox(_error!, onRetry: _load)
              : Column(children: [
                  Expanded(
                    child: ListView.builder(
                      itemCount: _symbols.length,
                      itemBuilder: (ctx, i) {
                        final s = _symbols[i];
                        final m = _byName[s];
                        return ListTile(
                          leading: CircleAvatar(child: Text('${i + 1}')),
                          title: Text(s),
                          subtitle: Text(m == null ? 'not in symbol list' : '${m['name']}  ·  last ${fmtNum(m['close'])}'),
                          trailing: TextButton(onPressed: () => _replace(i), child: const Text('Replace')),
                        );
                      },
                    ),
                  ),
                  if (_status.isNotEmpty) Padding(padding: const EdgeInsets.symmetric(horizontal: 16), child: Text(_status, style: const TextStyle(fontSize: 12))),
                  Padding(
                    padding: const EdgeInsets.all(16),
                    child: Row(children: [
                      Expanded(child: FilledButton.icon(onPressed: _dirty && !_saving ? _save : null, icon: const Icon(Icons.save), label: Text(_saving ? 'Saving...' : 'Save to server and regenerate'))),
                      const SizedBox(width: 8),
                      OutlinedButton(onPressed: _dirty ? _load : null, child: const Text('Undo')),
                    ]),
                  ),
                  const Padding(padding: EdgeInsets.fromLTRB(16, 0, 16, 12), child: Text('Replacing a stock rewrites the watchlist on the NAS and regenerates today\'s analysis (1-2 minutes). The self-scoring log keeps all past readings.', style: TextStyle(fontSize: 11))),
                ]),
    );
  }
}

class _SymbolSearch extends SearchDelegate<String?> {
  final List<Map<String, dynamic>> all;
  final List<String> exclude;
  _SymbolSearch(this.all, {required this.exclude}) : super(searchFieldLabel: 'Symbol or company name');

  @override
  List<Widget> buildActions(BuildContext context) => [IconButton(onPressed: () => query = '', icon: const Icon(Icons.clear))];
  @override
  Widget buildLeading(BuildContext context) => IconButton(onPressed: () => close(context, null), icon: const Icon(Icons.arrow_back));
  @override
  Widget buildResults(BuildContext context) => buildSuggestions(context);
  @override
  Widget buildSuggestions(BuildContext context) {
    final q = query.trim().toUpperCase();
    final hits = all.where((m) => !exclude.contains(m['symbol']) && (q.isEmpty || (m['symbol'] as String).contains(q) || (m['name'] as String).toUpperCase().contains(q))).take(60).toList();
    return ListView(children: [
      for (final m in hits)
        ListTile(title: Text(m['symbol']), subtitle: Text('${m['name']}  ·  last ${fmtNum(m['close'])}'), onTap: () => close(context, m['symbol'] as String)),
    ]);
  }
}
