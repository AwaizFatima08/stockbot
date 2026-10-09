import 'package:flutter/material.dart';
import '../api.dart';
import '../widgets/common.dart';
import 'stock.dart';

class OverviewScreen extends StatefulWidget {
  const OverviewScreen({super.key});
  @override
  State<OverviewScreen> createState() => _OverviewScreenState();
}

class _OverviewScreenState extends State<OverviewScreen> {
  late Future<Map<String, dynamic>> _f;
  @override
  void initState() {
    super.initState();
    _f = Api.instance.summary();
  }

  Future<void> _reload() async {
    setState(() => _f = Api.instance.summary());
    await _f;
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Stock Guru'), actions: [IconButton(onPressed: _reload, icon: const Icon(Icons.refresh))]),
      body: FutureBuilder<Map<String, dynamic>>(
        future: _f,
        builder: (ctx, snap) {
          if (snap.connectionState != ConnectionState.done) return const Center(child: CircularProgressIndicator());
          if (snap.hasError) return ErrorBox(snap.error!, onRetry: _reload);
          final s = snap.data!;
          final stocks = (s['stocks'] as List).cast<Map<String, dynamic>>();
          final problems = (s['data_problems'] as List?) ?? [];
          return RefreshIndicator(
            onRefresh: _reload,
            child: ListView(
              padding: const EdgeInsets.only(bottom: 24),
              children: [
                ListTile(
                  leading: Icon(s['data_ok'] == true ? Icons.check_circle : Icons.warning, color: s['data_ok'] == true ? Colors.green : Colors.orange),
                  title: Text('Daily performance - ${s['as_of']}'),
                  subtitle: Text((s['data_ok'] == true ? 'PSX end-of-day data OK' : 'Data problems: ${problems.join('; ')}') + (Api.instance.lastRoute.isEmpty ? '' : '  \u00b7  via ${Api.instance.lastRoute}')),
                ),
                for (final st in stocks) _StockCard(st),
                const Padding(padding: EdgeInsets.all(16), child: Text(kDisclaimer, style: TextStyle(fontSize: 11))),
              ],
            ),
          );
        },
      ),
    );
  }
}

class _StockCard extends StatelessWidget {
  final Map<String, dynamic> s;
  const _StockCard(this.s);
  @override
  Widget build(BuildContext context) {
    final ch = (s['change_pct'] as num?)?.toDouble();
    final color = ch == null ? Colors.grey : ch > 0 ? Colors.green : ch < 0 ? Colors.red : Colors.grey;
    final setups = (s['setups'] as List? ?? []).cast<String>();
    final patterns = (s['patterns'] as List? ?? []).cast<String>().where((p) => !setups.any((x) => x.toLowerCase().startsWith(p.toLowerCase()))).toList();
    final tags = <String>[...setups, ...patterns];
    return Card(
      margin: const EdgeInsets.symmetric(horizontal: 12, vertical: 5),
      child: InkWell(
        onTap: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => StockScreen(symbol: s['symbol'], name: s['name'] ?? ''))),
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Row(children: [
              Expanded(
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Text(s['symbol'], style: Theme.of(context).textTheme.titleMedium),
                  Text('${s['name'] ?? ''} · ${s['sector'] ?? ''}', style: Theme.of(context).textTheme.bodySmall, maxLines: 1, overflow: TextOverflow.ellipsis),
                ]),
              ),
              Column(crossAxisAlignment: CrossAxisAlignment.end, children: [
                Text(fmtNum(s['close']), style: Theme.of(context).textTheme.titleMedium),
                Text(fmtPct(s['change_pct']), style: TextStyle(color: color, fontWeight: FontWeight.w600)),
              ]),
            ]),
            const SizedBox(height: 6),
            Wrap(spacing: 6, runSpacing: -6, crossAxisAlignment: WrapCrossAlignment.center, children: [
              TrendChip(s['trend'] ?? 'unknown'),
              Text('RSI ${fmtNum(s['rsi'], d: 0)}', style: const TextStyle(fontSize: 12)),
              Text('Vol ${fmtNum(s['volume_ratio'], d: 1)}x', style: const TextStyle(fontSize: 12)),
              Text('1w ${fmtPct(s['ret_1w'], d: 1)}  1m ${fmtPct(s['ret_1m'], d: 1)}', style: const TextStyle(fontSize: 12)),
            ]),
            if (tags.isNotEmpty)
              Padding(
                padding: const EdgeInsets.only(top: 4),
                child: Wrap(spacing: 4, runSpacing: 4, children: [for (final t in tags) Chip(label: Text(t, style: const TextStyle(fontSize: 11)), visualDensity: VisualDensity.compact, padding: EdgeInsets.zero)]),
              ),
            if (s['agm_date'] != null || s['last_ex_dividend'] != null)
              Padding(
                padding: const EdgeInsets.only(top: 4),
                child: Text([if (s['agm_date'] != null) 'AGM ${s['agm_date']}', if (s['last_ex_dividend'] != null) 'last ex-div ${s['last_ex_dividend']}'].join('  ·  '),
                    style: Theme.of(context).textTheme.bodySmall),
              ),
            if ((s['problems'] as List?)?.isNotEmpty ?? false) Text('Problem: ${(s['problems'] as List).join('; ')}', style: const TextStyle(color: Colors.orange, fontSize: 12)),
          ]),
        ),
      ),
    );
  }
}
