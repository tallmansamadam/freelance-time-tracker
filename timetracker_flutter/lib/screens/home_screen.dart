import 'dart:async';
import 'dart:math';
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:uuid/uuid.dart';
import '../models/entry.dart';
import '../services/db_service.dart';
import '../services/sync_service.dart';

// ── Palette (matches Python app) ──────────────────────────────────────────────
const _palette = [
  Color(0xFF4A90D9), // Blue
  Color(0xFF2ECC71), // Green
  Color(0xFFE74C3C), // Red
  Color(0xFFF39C12), // Orange
  Color(0xFF9B59B6), // Purple
  Color(0xFFE91E8C), // Pink
  Color(0xFF1ABC9C), // Teal
  Color(0xFFF1C40F), // Yellow
];

// ── Particle model ────────────────────────────────────────────────────────────
class _Particle {
  double x, y, speed, size;
  int colorIdx;
  _Particle({required this.x, required this.y, required this.speed, required this.size, required this.colorIdx});
}

// ── Particle painter ──────────────────────────────────────────────────────────
class _ParticlePainter extends CustomPainter {
  final List<_Particle> particles;
  final double scanY;
  _ParticlePainter(this.particles, this.scanY);

  @override
  void paint(Canvas canvas, Size size) {
    // Scan line
    canvas.drawLine(
      Offset(0, scanY), Offset(size.width, scanY),
      Paint()..color = const Color(0xFF252B5A)..strokeWidth = 1,
    );

    for (final p in particles) {
      final base = _palette[p.colorIdx];
      final r = base.red, g = base.green, b = base.blue;

      // Trailing segments
      for (int i = 1; i <= 10; i++) {
        final tx   = p.x + i * 2.6;
        final fade = pow(1 - i / 11, 1.4).toDouble();
        final tr   = max(0.5, p.size * fade);
        canvas.drawCircle(
          Offset(tx, p.y),
          tr,
          Paint()..color = Color.fromARGB(255, (r * fade).round(), (g * fade).round(), (b * fade).round()),
        );
      }
      // Bright head
      canvas.drawCircle(Offset(p.x, p.y), p.size, Paint()..color = base);
    }
  }

  @override
  bool shouldRepaint(_ParticlePainter old) => true;
}

// ── Home screen ───────────────────────────────────────────────────────────────
class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});
  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  static const _bg2  = Color(0xFF16213E);
  static const _bg3  = Color(0xFF0F3460);

  // Timer state
  bool      _running   = false;
  DateTime? _startTime;
  int       _elapsed   = 0;
  Timer?    _ticker;

  // Color selection
  Color _selectedColor = _palette[0];

  // Input
  final _labelCtrl   = TextEditingController();
  final _commentCtrl = TextEditingController();

  // Particles
  final _rng       = Random();
  final _particles = <_Particle>[];
  double _scanY    = 0;
  Timer? _animTicker;
  double _canvasW  = 300;
  double _canvasH  = 60;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _initParticles());
  }

  void _initParticles() {
    for (int i = 0; i < 16; i++) {
      _particles.add(_Particle(
        x:        _rng.nextDouble() * _canvasW,
        y:        _rng.nextDouble() * (_canvasH - 6) + 3,
        speed:    _rng.nextDouble() * 1.7 + 0.5,
        size:     _rng.nextDouble() * 2.0 + 1.5,
        colorIdx: i % _palette.length,
      ));
    }
    _animTicker = Timer.periodic(const Duration(milliseconds: 33), (_) => _animTick());
  }

  void _animTick() {
    if (!mounted) return;
    setState(() {
      _scanY = (_scanY + 0.45) % _canvasH;
      for (final p in _particles) {
        p.x -= p.speed;
        if (p.x < -30) {
          p.x        = _canvasW + _rng.nextDouble() * 50 + 5;
          p.y        = _rng.nextDouble() * (_canvasH - 6) + 3;
          p.colorIdx = _rng.nextInt(_palette.length);
          p.speed    = _rng.nextDouble() * 1.7 + 0.5;
          p.size     = _rng.nextDouble() * 2.0 + 1.5;
        }
      }
    });
  }

  @override
  void dispose() {
    _ticker?.cancel();
    _animTicker?.cancel();
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
      setState(() => _elapsed = DateTime.now().difference(_startTime!).inSeconds);
    });
  }

  Future<void> _stop() async {
    _ticker?.cancel();
    final endTime = DateTime.now();
    setState(() => _running = false);

    final h = _elapsed ~/ 3600;
    final m = (_elapsed % 3600) ~/ 60;
    final s = _elapsed % 60;
    final durStr = '${h.toString().padLeft(2,'0')}:${m.toString().padLeft(2,'0')}:${s.toString().padLeft(2,'0')}';

    final colorHex = '#${_selectedColor.red.toRadixString(16).padLeft(2,'0')}'
                     '${_selectedColor.green.toRadixString(16).padLeft(2,'0')}'
                     '${_selectedColor.blue.toRadixString(16).padLeft(2,'0')}';

    final entry = Entry(
      syncId:       const Uuid().v4(),
      date:         _startTime!.toIso8601String().substring(0, 10),
      startTime:    _startTime!.toIso8601String().substring(11, 19),
      endTime:      endTime.toIso8601String().substring(11, 19),
      durationSecs: _elapsed,
      durationStr:  durStr,
      label:        _labelCtrl.text.trim(),
      tagColor:     colorHex,
      comment:      _commentCtrl.text.trim(),
    );

    await DbService.insertEntry(entry);
    SyncService.pushEntry(entry);
    setState(() => _elapsed = 0);
  }

  String get _timerStr {
    final h = _elapsed ~/ 3600;
    final m = (_elapsed % 3600) ~/ 60;
    final s = _elapsed % 60;
    return '${h.toString().padLeft(2,'0')}:${m.toString().padLeft(2,'0')}:${s.toString().padLeft(2,'0')}';
  }

  // Pulsing timer color
  Color get _timerColor {
    if (!_running) return const Color(0xFFE94560).withOpacity(0.6);
    final t = DateTime.now().millisecondsSinceEpoch % 1000 / 1000.0;
    final f = (sin(t * pi * 2) + 1) / 2;
    return Color.fromARGB(255, (0xE9 + 0x16 * f).round(), 0x45, 0x60);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('FREELANCE TIME TRACKER',
            style: TextStyle(fontSize: 14, fontWeight: FontWeight.bold)),
        // Particle visualizer in the app bar flex space
        flexibleSpace: Align(
          alignment: Alignment.bottomCenter,
          child: LayoutBuilder(
            builder: (_, constraints) {
              _canvasW = constraints.maxWidth;
              _canvasH = 56;
              return SizedBox(
                width: _canvasW,
                height: _canvasH,
                child: CustomPaint(
                  painter: _ParticlePainter(_particles, _scanY),
                ),
              );
            },
          ),
        ),
        actions: [
          IconButton(icon: const Icon(Icons.list_alt),    tooltip: 'Time Log',       onPressed: () => context.push('/log')),
          IconButton(icon: const Icon(Icons.receipt_long),tooltip: 'Create Invoice', onPressed: () => context.push('/invoice')),
          IconButton(icon: const Icon(Icons.settings),    tooltip: 'Settings',       onPressed: () => context.push('/settings')),
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
                  color: _timerColor,
                ),
              ),
            ),
            const SizedBox(height: 16),

            // Start / Stop buttons
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
            const SizedBox(height: 20),

            // Color palette
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
              decoration: BoxDecoration(color: _bg2, borderRadius: BorderRadius.circular(8)),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.spaceEvenly,
                children: _palette.map((c) {
                  final selected = c == _selectedColor;
                  return GestureDetector(
                    onTap: () => setState(() => _selectedColor = c),
                    child: AnimatedContainer(
                      duration: const Duration(milliseconds: 150),
                      width:  selected ? 30 : 24,
                      height: selected ? 30 : 24,
                      decoration: BoxDecoration(
                        color: c,
                        shape: BoxShape.circle,
                        border: selected ? Border.all(color: Colors.white, width: 2.5) : null,
                        boxShadow: selected ? [BoxShadow(color: c.withOpacity(0.6), blurRadius: 8)] : null,
                      ),
                    ),
                  );
                }).toList(),
              ),
            ),
            const SizedBox(height: 12),

            // Label + comment input card
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(color: _bg2, borderRadius: BorderRadius.circular(8)),
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
                  Divider(color: _bg3),
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
