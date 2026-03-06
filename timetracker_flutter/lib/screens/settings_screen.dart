import 'package:flutter/material.dart';

class SettingsScreen extends StatelessWidget {
  const SettingsScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('SETTINGS')),
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
