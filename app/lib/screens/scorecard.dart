import 'package:flutter/material.dart';
import '../api.dart';
import '../widgets/common.dart';

class ScorecardScreen extends StatefulWidget {
  const ScorecardScreen({super.key});
  @override
  State<ScorecardScreen> createState() => _ScorecardScreenState();
}

class _ScorecardScreenState extends State<ScorecardScreen> {
  late Future<Map<String, dynamic>> _f = Api.instance.scorecard();
  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Scorecard'), actions: [IconButton(onPressed: () => setState(() => _f = Api.instance.scorecard()), icon: const Icon(Icons.refresh))]),
      body: FutureBuilder<Map<String, dynamic>>(
        future: _f,
        builder: (ctx, snap) {
          if (snap.connectionState != ConnectionState.done) return const Center(child: CircularProgressIndicator());
          if (snap.hasError) return ErrorBox(snap.error!, onRetry: () => setState(() => _f = Api.instance.scorecard()));
          final md = snap.data!['markdown'].toString();
          final lines = md.split('\n');
          final widgets = <Widget>[];
          List<List<String>>? table;
          void flush() {
            if (table == null || table!.isEmpty) return;
            final t = table!;
            widgets.add(SingleChildScrollView(
              scrollDirection: Axis.horizontal,
              child: DataTable(
                columnSpacing: 14,
                headingTextStyle: const TextStyle(fontWeight: FontWeight.w700, fontSize: 12),
                dataTextStyle: const TextStyle(fontSize: 12),
                columns: [for (final c in t.first) DataColumn(label: Text(c))],
                rows: [for (final r in t.skip(1)) DataRow(cells: [for (var i = 0; i < t.first.length; i++) DataCell(Text(i < r.length ? r[i] : ''))])],
              ),
            ));
            table = null;
          }
          for (final raw in lines) {
            final l = raw.trim();
            if (l.startsWith('|')) {
              final cells = l.substring(1, l.endsWith('|') ? l.length - 1 : l.length).split('|').map((c) => c.trim()).toList();
              if (cells.every((c) => RegExp(r'^-+$').hasMatch(c))) continue;
              (table ??= []).add(cells);
              continue;
            }
            flush();
            if (l.isEmpty) continue;
            if (l.startsWith('# ')) {
              widgets.add(Padding(padding: const EdgeInsets.only(top: 8, bottom: 6), child: Text(l.substring(2), style: Theme.of(context).textTheme.titleLarge)));
            } else if (l.startsWith('## ')) {
              widgets.add(Padding(padding: const EdgeInsets.only(top: 12, bottom: 6), child: Text(l.substring(3), style: Theme.of(context).textTheme.titleMedium)));
            } else {
              widgets.add(Padding(padding: const EdgeInsets.only(bottom: 6), child: Text(l, style: const TextStyle(fontSize: 13))));
            }
          }
          flush();
          return ListView(padding: const EdgeInsets.all(16), children: [...widgets, const SizedBox(height: 12), const Text(kDisclaimer, style: TextStyle(fontSize: 11))]);
        },
      ),
    );
  }
}
