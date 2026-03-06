import 'dart:async';
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:uuid/uuid.dart';
import '../models/entry.dart';
import '../services/db_service.dart';
import '../services/sync_service.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});
  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  static const _accent    = Color(0xFFE94560);
  static const _bg2       = Color(0xFF16213E);
  static const _bg3       = Color(0xFF0F3460);
  static const _textMuted = Color(0xFF8A8AA0);

  bool      _running   = false;
  DateTime? _startTime;
  int       _elapsed   = 0;   // seconds
  Timer?    _ticker;

  final _labelCtrl   = TextEditingController();
  final _commentCtrl = TextEditingController();

  @override
  void dispose() {
    _ticker?.cancel();
    _labelCtrl.dispose();
    _commentCtrl.dispose();
    super.dispose();
  }

  void _start() {
    setState(() {
      _running   = true;
      _startTime = DateTime.now();
      _elapsed   = 0;
    });
    _ticker = Timer.periodic(const Duration(seconds: 1), (_) {
      setState(() {
        _elapsed = DateTime.now().difference(_startTime!).inSeconds;
      });
    });
  }

  Future<void> _stop() async {
    _ticker?.cancel();
    final endTime = DateTime.now();
    setState(() => _running = false);

    final h = _elapsed ~/ 3600;
    final m = (_elapsed % 3600) ~/ 60;
    final s = _elapsed % 60;
    final durStr = '${h.toString().padLeft(2,'0')}:'
                   '${m.toString().padLeft(2,'0')}:'
                   '${s.toString().padLeft(2,'0')}';

    final entry = Entry(
      syncId:       const Uuid().v4(),
      date:         _startTime!.toIso8601String().substring(0, 10),
      startTime:    _startTime!.toIso8601String().substring(11, 19),
      endTime:      endTime.toIso8601String().substring(11, 19),
      durationSecs: _elapsed,
      durationStr:  durStr,
      label:        _labelCtrl.text.trim(),
      tagColor:     '',
      comment:      _commentCtrl.text.trim(),
    );

    await DbService.insertEntry(entry);
    SyncService.pushEntry(entry);   // fire and forget

    setState(() => _elapsed = 0);
  }

  String get _timerStr {
    final h = _elapsed ~/ 3600;
    final m = (_elapsed % 3600) ~/ 60;
    final s = _elapsed % 60;
    return '${h.toString().padLeft(2,'0')}:'
           '${m.toString().padLeft(2,'0')}:'
           '${s.toString().padLeft(2,'0')}';
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('FREELANCE TIME TRACKER',
            style: TextStyle(fontSize: 14, fontWeight: FontWeight.bold)),
        actions: [
          IconButton(
            icon: const Icon(Icons.list_alt),
            tooltip: 'Time Log',
            onPressed: () => context.go('/log'),
          ),
          IconButton(
            icon: const Icon(Icons.receipt_long),
            tooltip: 'Create Invoice',
            onPressed: () => context.go('/invoice'),
          ),
          IconButton(
            icon: const Icon(Icons.settings),
            tooltip: 'Settings',
            onPressed: () => context.go('/settings'),
          ),
        ],
      ),
      body: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // Timer display
            Center(
              child: Text(
                _timerStr,
                style: TextStyle(
                  fontSize: 72,
                  fontFamily: 'Courier',
                  fontWeight: FontWeight.bold,
                  color: _running ? _accent : _accent.withOpacity(0.6),
                ),
              ),
            ),
            const SizedBox(height: 16),

            // Start / Stop
            Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                ElevatedButton.icon(
                  onPressed: _running ? null : _start,
                  icon: const Icon(Icons.play_arrow),
                  label: const Text('START'),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: const Color(0xFF27AE60),
                    padding: const EdgeInsets.symmetric(horizontal: 32, vertical: 14),
                  ),
                ),
                const SizedBox(width: 16),
                ElevatedButton.icon(
                  onPressed: _running ? _stop : null,
                  icon: const Icon(Icons.stop),
                  label: const Text('STOP'),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: const Color(0xFFC0392B),
                    padding: const EdgeInsets.symmetric(horizontal: 32, vertical: 14),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 24),

            // Input card
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: _bg2,
                borderRadius: BorderRadius.circular(8),
              ),
              child: Column(
                children: [
                  TextField(
                    controller: _labelCtrl,
                    decoration: const InputDecoration(
                      labelText: 'Project / Client',
                      labelStyle: TextStyle(color: Color(0xFF8A8AA0)),
                      border: InputBorder.none,
                    ),
                    style: const TextStyle(color: Colors.white),
                  ),
                  const Divider(color: Color(0xFF0F3460)),
                  TextField(
                    controller: _commentCtrl,
                    decoration: const InputDecoration(
                      labelText: 'Comment',
                      labelStyle: TextStyle(color: Color(0xFF8A8AA0)),
                      border: InputBorder.none,
                    ),
                    style: const TextStyle(color: Colors.white),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
