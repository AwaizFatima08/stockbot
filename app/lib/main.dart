import 'package:flutter/material.dart';
import 'api.dart';
import 'screens/overview.dart';
import 'screens/scorecard.dart';
import 'screens/settings.dart';
import 'screens/watchlist.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await Api.instance.load();
  runApp(const StockGuruApp());
}

class StockGuruApp extends StatelessWidget {
  const StockGuruApp({super.key});
  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Stock Guru',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(colorSchemeSeed: const Color(0xFF1B5E20), useMaterial3: true, brightness: Brightness.light),
      darkTheme: ThemeData(colorSchemeSeed: const Color(0xFF1B5E20), useMaterial3: true, brightness: Brightness.dark),
      home: const HomeShell(),
    );
  }
}

class HomeShell extends StatefulWidget {
  const HomeShell({super.key});
  @override
  State<HomeShell> createState() => _HomeShellState();
}

class _HomeShellState extends State<HomeShell> {
  int _tab = 0;
  @override
  Widget build(BuildContext context) {
    // Build only the selected tab so every visit re-fetches (settings changes take effect at once).
    final page = switch (_tab) {
      0 => const OverviewScreen(),
      1 => const ScorecardScreen(),
      2 => const WatchlistScreen(),
      _ => const SettingsScreen(),
    };
    return Scaffold(
      body: page,
      bottomNavigationBar: NavigationBar(
        selectedIndex: _tab,
        onDestinationSelected: (i) => setState(() => _tab = i),
        destinations: const [
          NavigationDestination(icon: Icon(Icons.insights_outlined), selectedIcon: Icon(Icons.insights), label: 'Today'),
          NavigationDestination(icon: Icon(Icons.fact_check_outlined), selectedIcon: Icon(Icons.fact_check), label: 'Scorecard'),
          NavigationDestination(icon: Icon(Icons.list_alt_outlined), selectedIcon: Icon(Icons.list_alt), label: 'Watchlist'),
          NavigationDestination(icon: Icon(Icons.settings_outlined), selectedIcon: Icon(Icons.settings), label: 'Settings'),
        ],
      ),
    );
  }
}
