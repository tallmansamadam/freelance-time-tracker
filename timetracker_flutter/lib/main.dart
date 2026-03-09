import 'package:flutter/material.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:supabase_flutter/supabase_flutter.dart';
import 'package:go_router/go_router.dart';
import 'package:sqflite_common_ffi/sqflite_ffi.dart';

import 'screens/home_screen.dart';
import 'screens/log_screen.dart';
import 'screens/invoice_screen.dart';
import 'screens/settings_screen.dart';
import 'services/sync_service.dart';

// ── Supabase credentials ───────────────────────────────────────────────────
// Replace with your actual Project URL and Anon Key from supabase.com
// (same project used by the Python desktop app)
const _supabaseUrl = 'https://ctexywwehfjdyamzuhpp.supabase.co';
const _supabaseKey = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImN0ZXh5d3dlaGZqZHlhbXp1aHBwIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzI3NTk2NjgsImV4cCI6MjA4ODMzNTY2OH0.etwTNaU4NJb0jJe0ygYDoZzCHtbKftFMAu2SFV-VNDo';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();

  // sqflite_common_ffi required for Windows/Linux/macOS desktop
  if (!kIsWeb && (defaultTargetPlatform == TargetPlatform.windows ||
                  defaultTargetPlatform == TargetPlatform.linux ||
                  defaultTargetPlatform == TargetPlatform.macOS)) {
    sqfliteFfiInit();
    databaseFactory = databaseFactoryFfi;
  }

  await Supabase.initialize(url: _supabaseUrl, anonKey: _supabaseKey);

  // Sync on startup: pull remote entries, then push any local pending ones
  await SyncService.pullEntries();
  await SyncService.pushPending();

  runApp(const ProviderScope(child: TimeTrackerApp()));
}

// ── Router ─────────────────────────────────────────────────────────────────
final _router = GoRouter(
  initialLocation: '/',
  routes: [
    GoRoute(path: '/',        builder: (_, __) => const HomeScreen()),
    GoRoute(path: '/log',     builder: (_, __) => const LogScreen()),
    GoRoute(path: '/invoice', builder: (_, __) => const InvoiceScreen()),
    GoRoute(path: '/settings',builder: (_, __) => const SettingsScreen()),
  ],
);

// ── App ────────────────────────────────────────────────────────────────────
class TimeTrackerApp extends StatelessWidget {
  const TimeTrackerApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp.router(
      title: 'Freelance Time Tracker',
      debugShowCheckedModeBanner: false,
      routerConfig: _router,
      theme: ThemeData.dark().copyWith(
        scaffoldBackgroundColor: const Color(0xFF1A1B2E),
        colorScheme: const ColorScheme.dark(
          primary:   Color(0xFFE94560),
          secondary: Color(0xFF0F3460),
          surface:   Color(0xFF16213E),
        ),
        appBarTheme: const AppBarTheme(
          backgroundColor: Color(0xFF16213E),
          foregroundColor: Color(0xFFEAEAEA),
          elevation: 0,
        ),
      ),
    );
  }
}
