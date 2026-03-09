import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

class SettingsScreen extends StatelessWidget {
  const SettingsScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('SETTINGS'),
        leading: BackButton(onPressed: () => context.pop()),
        actions: [
          IconButton(
            icon: const Icon(Icons.home),
            tooltip: 'Home',
            onPressed: () => context.go('/'),
          ),
        ],
      ),
      body: const Padding(
        padding: EdgeInsets.all(24),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Supabase URL and key are set in lib/main.dart.',
                style: TextStyle(color: Color(0xFF8A8AA0))),
            SizedBox(height: 8),
            Text('Replace YOUR_SUPABASE_URL and YOUR_SUPABASE_ANON_KEY with your '
                'project credentials from supabase.com.',
                style: TextStyle(color: Color(0xFF8A8AA0))),
          ],
        ),
      ),
    );
  }
}
