import 'package:flutter/material.dart';

class Section extends StatelessWidget {
  final String title;
  final Widget child;
  const Section({super.key, required this.title, required this.child});
  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.fromLTRB(16, 16, 16, 4),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(title, style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 8),
          child,
        ]),
      );
}

class Bullets extends StatelessWidget {
  final List<dynamic> items;
  const Bullets(this.items, {super.key});
  @override
  Widget build(BuildContext context) => Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          for (final t in items)
            Padding(
              padding: const EdgeInsets.only(bottom: 6),
              child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                const Text('•  '),
                Expanded(child: Text(t.toString())),
              ]),
            ),
        ],
      );
}

class KV extends StatelessWidget {
  final List<MapEntry<String, String>> rows;
  const KV(this.rows, {super.key});
  @override
  Widget build(BuildContext context) => Table(
        columnWidths: const {0: FlexColumnWidth(1.3), 1: FlexColumnWidth(1)},
        children: [
          for (final r in rows)
            TableRow(children: [
              Padding(padding: const EdgeInsets.symmetric(vertical: 4), child: Text(r.key, style: TextStyle(color: Theme.of(context).colorScheme.onSurfaceVariant))),
              Padding(padding: const EdgeInsets.symmetric(vertical: 4), child: Text(r.value, textAlign: TextAlign.right, style: const TextStyle(fontWeight: FontWeight.w600))),
            ]),
        ],
      );
}

class TrendChip extends StatelessWidget {
  final String trend;
  const TrendChip(this.trend, {super.key});
  @override
  Widget build(BuildContext context) {
    final (label, color) = switch (trend) {
      'uptrend' => ('Uptrend', Colors.green),
      'downtrend' => ('Downtrend', Colors.red),
      'mixed' => ('Mixed', Colors.orange),
      _ => ('Unknown', Colors.grey),
    };
    return Chip(
      label: Text(label, style: const TextStyle(fontSize: 12)),
      backgroundColor: color.withValues(alpha: 0.15),
      side: BorderSide(color: color.withValues(alpha: 0.5)),
      visualDensity: VisualDensity.compact,
      padding: EdgeInsets.zero,
    );
  }
}

class ErrorBox extends StatelessWidget {
  final Object error;
  final VoidCallback? onRetry;
  const ErrorBox(this.error, {super.key, this.onRetry});
  @override
  Widget build(BuildContext context) => Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(mainAxisSize: MainAxisSize.min, children: [
            const Icon(Icons.cloud_off, size: 40),
            const SizedBox(height: 12),
            Text('Could not reach the Stock Guru server.\n$error', textAlign: TextAlign.center),
            const SizedBox(height: 8),
            const Text('Check the server address and token in Settings, and that the phone is on the home network.', textAlign: TextAlign.center, style: TextStyle(fontSize: 12)),
            if (onRetry != null) TextButton(onPressed: onRetry, child: const Text('Retry')),
          ]),
        ),
      );
}

const kDisclaimer = 'Personal research tool. Everything here describes data and history; nothing is advice or a forecast.';
