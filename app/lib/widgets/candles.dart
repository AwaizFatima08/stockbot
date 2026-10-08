import 'dart:math';
import 'package:flutter/material.dart';

/// Candlestick chart drawn from OHLC rows: {d,o,h,l,c,v}. Shows the last [count] sessions
/// with 20- and 50-session simple moving averages (computed over the full series).
class CandleChart extends StatelessWidget {
  final List<dynamic> rows;
  final int count;
  const CandleChart({super.key, required this.rows, this.count = 120});

  @override
  Widget build(BuildContext context) {
    if (rows.length < 5) return const SizedBox(height: 120, child: Center(child: Text('Not enough history')));
    return LayoutBuilder(builder: (ctx, c) {
      return CustomPaint(
        size: Size(c.maxWidth, 300),
        painter: _CandlePainter(rows, count, Theme.of(context).colorScheme.onSurface, Theme.of(context).colorScheme.outlineVariant),
      );
    });
  }
}

class _CandlePainter extends CustomPainter {
  final List<dynamic> rows;
  final int count;
  final Color fg;
  final Color grid;
  _CandlePainter(this.rows, this.count, this.fg, this.grid);

  List<double?> _sma(List<double> v, int n) {
    final out = List<double?>.filled(v.length, null);
    double run = 0;
    for (var i = 0; i < v.length; i++) {
      run += v[i];
      if (i >= n) run -= v[i - n];
      if (i >= n - 1) out[i] = run / n;
    }
    return out;
  }

  @override
  void paint(Canvas canvas, Size size) {
    final closesAll = rows.map((r) => ((r['c'] ?? 0) as num).toDouble()).toList();
    final s20 = _sma(closesAll, 20), s50 = _sma(closesAll, 50);
    final n = min(count, rows.length);
    final start = rows.length - n;
    final slice = rows.sublist(start);
    const padL = 44.0, padR = 8.0, padT = 8.0, volH = 50.0, padB = 24.0;
    final priceH = size.height - padT - volH - padB;
    double lo = double.infinity, hi = -double.infinity, vmax = 0;
    for (final r in slice) {
      final l = ((r['l'] ?? 0) as num).toDouble(), h = ((r['h'] ?? 0) as num).toDouble();
      if (l > 0) lo = min(lo, l);
      if (h > 0) hi = max(hi, h);
      vmax = max(vmax, ((r['v'] ?? 0) as num).toDouble());
    }
    if (!lo.isFinite || !hi.isFinite || hi <= lo) return;
    final pad = (hi - lo) * 0.05;
    lo -= pad;
    hi += pad;
    final w = (size.width - padL - padR) / n;
    double y(double p) => padT + (hi - p) / (hi - lo) * priceH;
    double x(int i) => padL + i * w + w / 2;

    // grid + axis labels
    final gridP = Paint()..color = grid..strokeWidth = 0.5;
    final tp = TextPainter(textDirection: TextDirection.ltr);
    for (var k = 0; k <= 4; k++) {
      final p = lo + (hi - lo) * k / 4;
      canvas.drawLine(Offset(padL, y(p)), Offset(size.width - padR, y(p)), gridP);
      tp.text = TextSpan(text: p.toStringAsFixed(p > 100 ? 0 : 2), style: TextStyle(color: fg, fontSize: 9));
      tp.layout();
      tp.paint(canvas, Offset(2, y(p) - 5));
    }
    // candles + volume
    final up = Paint()..color = const Color(0xFF2E7D32);
    final down = Paint()..color = const Color(0xFFC62828);
    for (var i = 0; i < n; i++) {
      final r = slice[i];
      final o = ((r['o'] ?? 0) as num).toDouble(), h = ((r['h'] ?? 0) as num).toDouble(), l = ((r['l'] ?? 0) as num).toDouble(), c = ((r['c'] ?? 0) as num).toDouble();
      if (h <= 0 || l <= 0) continue;
      final p = c >= o ? up : down;
      canvas.drawLine(Offset(x(i), y(h)), Offset(x(i), y(l)), p..strokeWidth = 1);
      final top = y(max(o, c)), bot = y(min(o, c));
      canvas.drawRect(Rect.fromLTRB(x(i) - w * 0.35, top, x(i) + w * 0.35, max(bot, top + 1)), p);
      final v = ((r['v'] ?? 0) as num).toDouble();
      if (vmax > 0) {
        final vh = v / vmax * (volH - 4);
        canvas.drawRect(Rect.fromLTRB(x(i) - w * 0.35, size.height - padB - vh, x(i) + w * 0.35, size.height - padB), p..color = p.color.withValues(alpha: 0.5));
      }
    }
    // SMAs
    void line(List<double?> s, Color col) {
      final path = Path();
      var started = false;
      for (var i = 0; i < n; i++) {
        final v = s[start + i];
        if (v == null) continue;
        if (!started) {
          path.moveTo(x(i), y(v));
          started = true;
        } else {
          path.lineTo(x(i), y(v));
        }
      }
      canvas.drawPath(path, Paint()..color = col..style = PaintingStyle.stroke..strokeWidth = 1.3);
    }
    line(s20, const Color(0xFF1565C0));
    line(s50, const Color(0xFFEF6C00));
    // date labels
    for (var i = 0; i < n; i += max(1, n ~/ 4)) {
      tp.text = TextSpan(text: slice[i]['d'].toString().substring(5), style: TextStyle(color: fg, fontSize: 9));
      tp.layout();
      tp.paint(canvas, Offset(x(i) - 12, size.height - padB + 6));
    }
    tp.text = TextSpan(children: [
      const TextSpan(text: '— SMA20  ', style: TextStyle(color: Color(0xFF1565C0), fontSize: 10)),
      const TextSpan(text: '— SMA50', style: TextStyle(color: Color(0xFFEF6C00), fontSize: 10)),
    ]);
    tp.layout();
    tp.paint(canvas, Offset(padL + 4, padT));
  }

  @override
  bool shouldRepaint(covariant _CandlePainter old) => old.rows != rows || old.count != count;
}
