import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';
import '../api.dart';
import '../widgets/candles.dart';
import '../widgets/common.dart';

class StockScreen extends StatefulWidget {
  final String symbol;
  final String name;
  const StockScreen({super.key, required this.symbol, required this.name});
  @override
  State<StockScreen> createState() => _StockScreenState();
}

class _StockScreenState extends State<StockScreen> {
  late Future<Map<String, dynamic>> _f;
  @override
  void initState() {
    super.initState();
    _f = Api.instance.stock(widget.symbol);
  }

  @override
  Widget build(BuildContext context) {
    return DefaultTabController(
      length: 6,
      child: Scaffold(
        appBar: AppBar(
          title: Text('${widget.symbol}  ${widget.name}', overflow: TextOverflow.ellipsis),
          bottom: const TabBar(isScrollable: true, tabAlignment: TabAlignment.start, tabs: [
            Tab(text: 'Today'),
            Tab(text: 'Chart & trends'),
            Tab(text: 'History'),
            Tab(text: 'Corporate'),
            Tab(text: 'Next week'),
            Tab(text: 'Long term'),
          ]),
        ),
        body: FutureBuilder<Map<String, dynamic>>(
          future: _f,
          builder: (ctx, snap) {
            if (snap.connectionState != ConnectionState.done) return const Center(child: CircularProgressIndicator());
            if (snap.hasError) return ErrorBox(snap.error!, onRetry: () => setState(() => _f = Api.instance.stock(widget.symbol)));
            final d = snap.data!;
            return TabBarView(children: [
              _TodayTab(d),
              _ChartTab(d, widget.symbol),
              _HistoryTab(d, widget.symbol),
              _CorporateTab(d),
              _OutlookTab(d),
              _LongTermTab(d),
            ]);
          },
        ),
      ),
    );
  }
}

class _TodayTab extends StatelessWidget {
  final Map<String, dynamic> d;
  const _TodayTab(this.d);
  @override
  Widget build(BuildContext context) {
    final s = d['snapshot'] as Map<String, dynamic>;
    final br = (s['base_rates'] as List? ?? []).cast<Map<String, dynamic>>();
    return ListView(children: [
      Section(
        title: 'Close ${fmtNum(s['close'])}  (${fmtPct(s['change_pct'])})  ·  ${d['as_of']}',
        child: Row(children: [TrendChip(s['trend'] ?? 'unknown'), const SizedBox(width: 8), Text('RSI14 ${fmtNum(s['rsi'], d: 0)}  ·  Volume ${fmtNum(s['volume_ratio'], d: 1)}x 20-day avg')]),
      ),
      Section(
        title: 'Key numbers',
        child: KV([
          MapEntry('Open / High / Low', '${fmtNum(s['open'])} / ${fmtNum(s['high'])} / ${fmtNum(s['low'])}'),
          MapEntry('Volume', fmtNum(s['volume'], d: 0)),
          MapEntry('SMA20 / SMA50', '${fmtNum(s['sma_short'])} / ${fmtNum(s['sma_long'])}'),
          MapEntry('1w / 1m / 3m', '${fmtPct(s['ret_1w'], d: 1)} / ${fmtPct(s['ret_1m'], d: 1)} / ${fmtPct(s['ret_3m'], d: 1)}'),
          MapEntry('52-week range', '${fmtNum(s['low_52w'])} - ${fmtNum(s['high_52w'])}'),
          MapEntry('Below 52w high', fmtPct(s['off_high_pct'], d: 1, sign: false)),
        ]),
      ),
      Section(title: 'In plain words', child: Bullets(s['sentences'] as List? ?? [])),
      if ((s['problems'] as List?)?.isNotEmpty ?? false) Section(title: 'Warnings', child: Bullets(s['problems'] as List)),
      Section(
        title: 'Setups that fired today',
        child: br.isEmpty
            ? const Text('None of the defined setups fired today.')
            : Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                for (final b in br) ...[
                  Text('${b['label']}  (conventionally ${b['bias']})', style: const TextStyle(fontWeight: FontWeight.w600)),
                  const SizedBox(height: 4),
                  Bullets([...(b['symbol'] as List), ...(b['universe'] as List)]),
                  const SizedBox(height: 8),
                ],
                const Text('Base rates describe what followed past occurrences. They are not forecasts; small samples mean little.', style: TextStyle(fontSize: 12)),
              ]),
      ),
      const Padding(padding: EdgeInsets.all(16), child: Text(kDisclaimer, style: TextStyle(fontSize: 11))),
    ]);
  }
}

class _ChartTab extends StatefulWidget {
  final Map<String, dynamic> d;
  final String symbol;
  const _ChartTab(this.d, this.symbol);
  @override
  State<_ChartTab> createState() => _ChartTabState();
}

class _ChartTabState extends State<_ChartTab> {
  int _count = 120;
  @override
  Widget build(BuildContext context) {
    final rows = widget.d['history_recent'] as List? ?? [];
    final s = widget.d['snapshot'] as Map<String, dynamic>;
    final patterns = (s['patterns'] as List? ?? []).cast<Map<String, dynamic>>();
    return ListView(children: [
      Padding(
        padding: const EdgeInsets.fromLTRB(16, 12, 16, 0),
        child: SegmentedButton<int>(
          segments: const [ButtonSegment(value: 60, label: Text('60')), ButtonSegment(value: 120, label: Text('120')), ButtonSegment(value: 250, label: Text('250'))],
          selected: {_count},
          onSelectionChanged: (v) => setState(() => _count = v.first),
        ),
      ),
      Padding(padding: const EdgeInsets.all(8), child: CandleChart(rows: rows, count: _count)),
      Section(title: 'Trend reading', child: Row(children: [TrendChip(s['trend'] ?? 'unknown'), const SizedBox(width: 8), Expanded(child: Text((s['sentences'] as List?)?.cast<String>().firstWhere((t) => t.contains('moving averages') || t.contains('trend'), orElse: () => '') ?? ''))])),
      Section(
        title: 'Candlestick patterns on the last session',
        child: patterns.isEmpty ? const Text('No pattern detected on the last candle.') : Bullets(patterns.map((p) => '${p['label']}: ${p['text']}').toList()),
      ),
      if (widget.d['chart'] != null)
        Section(
          title: 'Annotated chart from the NAS',
          child: InteractiveViewer(
            child: Image.network(Api.instance.chartUrl(widget.symbol), headers: {'X-Token': Api.instance.token}, errorBuilder: (_, __, ___) => const Text('Chart image not available')),
          ),
        ),
    ]);
  }
}

class _HistoryTab extends StatefulWidget {
  final Map<String, dynamic> d;
  final String symbol;
  const _HistoryTab(this.d, this.symbol);
  @override
  State<_HistoryTab> createState() => _HistoryTabState();
}

class _HistoryTabState extends State<_HistoryTab> {
  List<dynamic>? _all;
  bool _loading = false;
  @override
  Widget build(BuildContext context) {
    final rows = (_all ?? widget.d['history_recent'] as List).reversed.toList();
    return Column(children: [
      Padding(
        padding: const EdgeInsets.all(8),
        child: Row(children: [
          Text('${rows.length} sessions', style: Theme.of(context).textTheme.bodySmall),
          const Spacer(),
          if (_all == null)
            TextButton.icon(
              onPressed: _loading
                  ? null
                  : () async {
                      setState(() => _loading = true);
                      try {
                        final h = await Api.instance.history(widget.symbol);
                        setState(() => _all = h['rows'] as List);
                      } catch (e) {
                        if (context.mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e')));
                      } finally {
                        if (mounted) setState(() => _loading = false);
                      }
                    },
              icon: const Icon(Icons.history),
              label: Text(_loading ? 'Loading...' : 'Load full history (since 2020)'),
            ),
        ]),
      ),
      Expanded(
        child: ListView.builder(
          itemCount: rows.length + 1,
          itemBuilder: (ctx, i) {
            if (i == 0) return const _HistRow(['Date', 'Open', 'High', 'Low', 'Close', 'Volume'], header: true);
            final r = rows[i - 1] as Map<String, dynamic>;
            return _HistRow([r['d'].toString(), fmtNum(r['o']), fmtNum(r['h']), fmtNum(r['l']), fmtNum(r['c']), fmtNum(r['v'], d: 0)]);
          },
        ),
      ),
    ]);
  }
}

class _HistRow extends StatelessWidget {
  final List<String> cells;
  final bool header;
  const _HistRow(this.cells, {this.header = false});
  @override
  Widget build(BuildContext context) {
    final style = TextStyle(fontSize: 11, fontWeight: header ? FontWeight.w700 : FontWeight.normal, fontFeatures: const [FontFeature.tabularFigures()]);
    return Container(
      color: header ? Theme.of(context).colorScheme.surfaceContainerHighest : null,
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 5),
      child: Row(children: [
        SizedBox(width: 78, child: Text(cells[0], style: style)),
        for (var i = 1; i < cells.length; i++) Expanded(child: Text(cells[i], style: style, textAlign: TextAlign.right)),
      ]),
    );
  }
}

String _payoutLabel(Map<String, dynamic> u) {
  final parts = <String>[];
  if (u['dividend_per_share'] != null) parts.add('Rs ${fmtNum(u['dividend_per_share'])} per share cash (${fmtNum(u['dividend_pct'], d: 0)}% of face value)');
  if (u['bonus_pct'] != null) parts.add('bonus ${fmtNum(u['bonus_pct'], d: 0)}%');
  if (u['right_pct'] != null) parts.add('right ${fmtNum(u['right_pct'], d: 1)}%');
  return parts.isEmpty ? (u['payout_text']?.toString() ?? 'Nil') : parts.join(', ');
}

class _CorporateTab extends StatelessWidget {
  final Map<String, dynamic> d;
  const _CorporateTab(this.d);
  Future<void> _open(String path) async {
    final u = Uri.parse(path.startsWith('http') ? path : 'https://dps.psx.com.pk$path');
    if (!await launchUrl(u, mode: LaunchMode.externalApplication)) {}
  }

  @override
  Widget build(BuildContext context) {
    final c = d['corporate'] as Map<String, dynamic>;
    final agm = c['agm_notice'] as Map<String, dynamic>?;
    final res = c['latest_result'] as Map<String, dynamic>?;
    final bm = c['latest_board_meeting'] as Map<String, dynamic>?;
    final ann = (c['announcements'] as List? ?? []).cast<Map<String, dynamic>>();
    final exDates = (c['ex_dates'] as List? ?? []).cast<Map<String, dynamic>>().reversed.toList();
    return ListView(children: [
      Section(
        title: c['company_name'] ?? '',
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(c['sector'] ?? '', style: Theme.of(context).textTheme.bodySmall),
          if ((c['business'] ?? '').toString().isNotEmpty) Padding(padding: const EdgeInsets.only(top: 6), child: Text('${c['business']}${(c['business'] as String).length >= 600 ? ' ...' : ''}', style: const TextStyle(fontSize: 13))),
        ]),
      ),
      Section(
        title: 'AGM',
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          KV([
            MapEntry('AGM date', c['agm_date']?.toString() ?? (agm == null ? 'no notice in recent announcements' : 'see notice (date not machine-readable)')),
            if (agm != null) MapEntry('Notice posted', agm['date'].toString()),
            MapEntry('Fiscal year end', c['fiscal_year_end']?.toString() ?? 'n/a'),
          ]),
          if (agm?['pdf'] != null) TextButton.icon(onPressed: () => _open(agm!['pdf']), icon: const Icon(Icons.picture_as_pdf), label: const Text('Open AGM notice (PSX)')),
        ]),
      ),
      Section(
        title: 'Declared payouts (ksestocks mirror of PSX notices)',
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          for (final u in (c['upcoming'] as List? ?? []).cast<Map<String, dynamic>>())
            ListTile(
              dense: true, contentPadding: EdgeInsets.zero,
              leading: const Icon(Icons.upcoming, color: Colors.green),
              title: Text(_payoutLabel(u), style: const TextStyle(fontWeight: FontWeight.w600)),
              subtitle: Text('Book closure ${u['bc_from']} to ${u['bc_to'] ?? '?'} (goes ex on ${u['bc_from']})'),
            ),
          if (c['last_dividend'] != null)
            ListTile(
              dense: true, contentPadding: EdgeInsets.zero,
              leading: const Icon(Icons.payments_outlined),
              title: Text('Last dividend: ${_payoutLabel(c['last_dividend'] as Map<String, dynamic>)}', style: const TextStyle(fontWeight: FontWeight.w600)),
              subtitle: Text('Book closure ${c['last_dividend']['bc_from']} to ${c['last_dividend']['bc_to'] ?? '?'}'),
            ),
          for (final u in (c['announced_undated'] as List? ?? []).cast<Map<String, dynamic>>())
            ListTile(dense: true, contentPadding: EdgeInsets.zero, leading: const Icon(Icons.campaign_outlined), title: Text('Announced, dates pending: ${_payoutLabel(u)}')),
          if ((c['upcoming'] as List? ?? []).isEmpty && c['last_dividend'] == null && (c['announced_undated'] as List? ?? []).isEmpty)
            const Text('No payout recorded since tracking began (8 Oct 2026). History fills in as book closures are announced.', style: TextStyle(fontSize: 12)),
          if (c['dividends_per_share_12m'] != null)
            Padding(padding: const EdgeInsets.only(top: 4), child: Text('Dividends tracked in the last 12 months: Rs ${fmtNum(c['dividends_per_share_12m'])} per share (${c['n_dividends_12m_tracked']} payouts, since tracking began)', style: const TextStyle(fontSize: 12))),
          if ((c['payout_history'] as List? ?? []).length > 1)
            Padding(padding: const EdgeInsets.only(top: 6), child: Wrap(spacing: 6, runSpacing: 4, children: [for (final h in (c['payout_history'] as List).cast<Map<String, dynamic>>()) Chip(label: Text('${h['bc_from']}  ${h['payout_text']}', style: const TextStyle(fontSize: 11)), visualDensity: VisualDensity.compact)])),
          Padding(padding: const EdgeInsets.only(top: 4), child: Text(c['payout_source'] ?? '', style: Theme.of(context).textTheme.bodySmall)),
        ]),
      ),
      Section(
        title: 'Ex-dividend record (XD markers in PSX daily files since 2020)',
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          KV([
            MapEntry('Last ex-dividend date', c['last_ex_dividend']?.toString() ?? 'none since 2020'),
            MapEntry('Ex-dividend dates, last 12 months', '${c['ex_dividends_last_12m'] ?? 0}'),
            MapEntry('Ex-dividend dates, last 3 years', '${c['ex_dividends_last_3y'] ?? 0}'),
            MapEntry('Last ex-bonus', c['last_ex_bonus']?.toString() ?? '-'),
            MapEntry('Last ex-right', c['last_ex_right']?.toString() ?? '-'),
          ]),
          if (exDates.isNotEmpty) Padding(padding: const EdgeInsets.only(top: 6), child: Wrap(spacing: 6, runSpacing: 4, children: [for (final e in exDates) Chip(label: Text('${e['date']} ${(e['kinds'] as List).join('/')}', style: const TextStyle(fontSize: 11)), visualDensity: VisualDensity.compact)])),
        ]),
      ),
      Section(
        title: 'Latest results and board meeting',
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          if (res != null) ListTile(dense: true, contentPadding: EdgeInsets.zero, leading: const Icon(Icons.description), title: Text(res['title']), subtitle: Text(res['date']), onTap: res['pdf'] == null ? null : () => _open(res['pdf'])),
          if (bm != null) ListTile(dense: true, contentPadding: EdgeInsets.zero, leading: const Icon(Icons.event), title: Text(bm['title']), subtitle: Text(bm['date']), onTap: bm['pdf'] == null ? null : () => _open(bm['pdf'])),
          if (res == null && bm == null) const Text('No announcements captured.'),
        ]),
      ),
      Section(
        title: 'Recent announcements (PSX)',
        child: Column(children: [
          for (final a in ann)
            ListTile(dense: true, contentPadding: EdgeInsets.zero, title: Text(a['title'], style: const TextStyle(fontSize: 13)), subtitle: Text('${a['date']} · ${a['category']}'), trailing: a['pdf'] != null ? const Icon(Icons.open_in_new, size: 16) : null, onTap: a['pdf'] == null ? null : () => _open(a['pdf'])),
          TextButton(onPressed: () => _open(c['source']), child: const Text('Company page on PSX Data Portal')),
        ]),
      ),
    ]);
  }
}

class _OutlookTab extends StatelessWidget {
  final Map<String, dynamic> d;
  const _OutlookTab(this.d);
  @override
  Widget build(BuildContext context) {
    final o = d['outlook'] as Map<String, dynamic>?;
    if (o == null) return const Center(child: Text('No data for this session.'));
    final dist = o['weekly_distribution'] as Map<String, dynamic>?;
    final levels = (o['levels'] as List? ?? []).cast<Map<String, dynamic>>();
    return ListView(children: [
      const Padding(
        padding: EdgeInsets.fromLTRB(16, 12, 16, 0),
        child: Text('Not a prediction. This shows what history says about the current readings, the typical size of a week, and which levels would confirm or break the picture.', style: TextStyle(fontSize: 12)),
      ),
      Section(title: 'What the data says', child: Bullets(o['sentences'] as List? ?? [])),
      if (dist != null)
        Section(
          title: 'Typical week (last 3 years, ${dist['n_weeks']} weeks)',
          child: KV([
            MapEntry('Median weekly move', fmtPct(dist['median_pct'], d: 1)),
            MapEntry('Middle half of weeks', '${fmtPct(dist['p25_pct'], d: 1)} to ${fmtPct(dist['p75_pct'], d: 1)}'),
            MapEntry('Worst 1 in 10 weeks', 'below ${fmtPct(dist['p10_pct'], d: 1)}'),
            MapEntry('Best 1 in 10 weeks', 'above ${fmtPct(dist['p90_pct'], d: 1)}'),
            MapEntry('Weeks that ended higher', fmtPct(dist['up_weeks_pct'], d: 0, sign: false)),
          ]),
        ),
      Section(
        title: 'Levels to watch',
        child: Column(children: [
          for (final l in levels)
            ListTile(
              dense: true,
              contentPadding: EdgeInsets.zero,
              title: Text('${l['label']}  ${fmtNum(l['level'])}  (${fmtPct(l['distance_pct'], d: 1)})', style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 13)),
              subtitle: Text(l['meaning']),
            ),
        ]),
      ),
    ]);
  }
}

/// A table row padded or cut to exactly [n] value cells so every row matches the header.
TableRow _row(String label, List values, int n, int decimals, double size) {
  final cells = List<dynamic>.generate(n, (i) => i < values.length ? values[i] : null);
  return TableRow(children: [
    Text(label, style: TextStyle(fontSize: size)),
    for (final v in cells) Text(fmtNum(v, d: decimals), textAlign: TextAlign.right, style: TextStyle(fontSize: size)),
  ]);
}

class _LongTermTab extends StatelessWidget {
  final Map<String, dynamic> d;
  const _LongTermTab(this.d);
  @override
  Widget build(BuildContext context) {
    final lt = d['longterm'] as Map<String, dynamic>;
    final p = lt['price'] as Map<String, dynamic>;
    final f = lt['fundamentals'] as Map<String, dynamic>;
    final years = (f['years'] as List? ?? []).cast<String>();
    final eps = (f['eps'] as List? ?? []);
    final pat = (f['profit_after_tax_000'] as List? ?? []);
    final sales = (f['sales_000'] as List? ?? []);
    final ratios = (f['ratios'] as Map<String, dynamic>? ?? {});
    return ListView(children: [
      const Padding(padding: EdgeInsets.fromLTRB(16, 12, 16, 0), child: Text('Long-term prospects here means the record: what the price and the reported results have actually done. No projections.', style: TextStyle(fontSize: 12))),
      Section(title: 'The record in plain words', child: Bullets(lt['sentences'] as List? ?? [])),
      Section(
        title: 'Price statistics',
        child: KV([
          MapEntry('Data since', '${p['first_date'] ?? 'n/a'} (${p['years_of_data'] ?? '?'} yrs)'),
          MapEntry('Return 1y / 3y / 5y', '${fmtPct(p['return_1y_pct'], d: 0)} / ${fmtPct(p['return_3y_pct'], d: 0)} / ${fmtPct(p['return_5y_pct'], d: 0)}'),
          MapEntry('Annual growth rate 3y / 5y', '${fmtPct(p['cagr_3y_pct'], d: 1)} / ${fmtPct(p['cagr_5y_pct'], d: 1)}'),
          MapEntry('Volatility (1y, annualised)', fmtPct(p['volatility_1y_pct'], d: 0, sign: false)),
          MapEntry('Max drawdown (3y)', fmtPct(p['max_drawdown_3y_pct'], d: 0)),
          MapEntry('From 3y high', fmtPct(p['drawdown_from_3y_high_pct'], d: 0)),
          MapEntry('1-year windows ended higher', fmtPct(p['positive_year_windows_pct'], d: 0, sign: false)),
        ]),
      ),
      if (f['available'] == true)
        Section(
          title: 'Reported results (PSX portal, 000s except EPS)',
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            KV([
              MapEntry('P/E (trailing)', fmtNum(f['pe_ttm'], d: 1)),
              MapEntry('Market cap (PKR bn)', fmtNum(f['market_cap_bn'], d: 1)),
              MapEntry('Free float', fmtPct(f['free_float_pct'], d: 0, sign: false)),
              MapEntry('EPS growth (compounded)', fmtPct(f['eps_cagr_pct'], d: 1)),
              MapEntry('Profitable years', '${f['profitable_years'] ?? '-'} of ${eps.length}'),
            ]),
            const SizedBox(height: 10),
            if (years.isNotEmpty)
              Table(
                border: TableBorder(horizontalInside: BorderSide(color: Theme.of(context).colorScheme.outlineVariant)),
                children: [
                  TableRow(children: [const Text(''), for (final y in years) Text(y, textAlign: TextAlign.right, style: const TextStyle(fontWeight: FontWeight.w700))]),
                  _row('EPS', eps, years.length, 2, 13),
                  _row('Profit', pat, years.length, 0, 11),
                  _row('Sales', sales, years.length, 0, 11),
                  for (final e in ratios.entries.where((e) => e.key != 'years' && e.value is List)) _row(e.key, e.value as List, years.length, 2, 11),
                ],
              ),
          ]),
        )
      else
        const Section(title: 'Reported results', child: Text('Company page not captured yet.')),
    ]);
  }
}
