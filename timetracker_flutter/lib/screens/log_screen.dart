import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:uuid/uuid.dart';
import 'package:pdf/pdf.dart';
import 'package:pdf/widgets.dart' as pw;
import 'package:printing/printing.dart';
import '../models/entry.dart';
import '../services/db_service.dart';
import '../services/sync_service.dart';

// ── Palette (matches Python app + home screen) ────────────────────────────────
const _palette = [
  Color(0xFF4A90D9),
  Color(0xFF2ECC71),
  Color(0xFFE74C3C),
  Color(0xFFF39C12),
  Color(0xFF9B59B6),
  Color(0xFFE91E8C),
  Color(0xFF1ABC9C),
  Color(0xFFF1C40F),
];

Color _parseHex(String hex) {
  if (hex.isEmpty) return const Color(0xFF8A8AA0);
  final h = hex.startsWith('#') ? hex.substring(1) : hex;
  if (h.length != 6) return const Color(0xFF8A8AA0);
  return Color(int.parse(h, radix: 16) | 0xFF000000);
}

String _fmtHours(int secs) {
  final h = secs ~/ 3600;
  final m = (secs % 3600) ~/ 60;
  return '${h}h ${m.toString().padLeft(2, '0')}m';
}

class LogScreen extends StatefulWidget {
  const LogScreen({super.key});
  @override
  State<LogScreen> createState() => _LogScreenState();
}

class _LogScreenState extends State<LogScreen> {
  List<Entry> _entries = [];

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final rows = await DbService.allEntries();
    setState(() => _entries = rows);
  }

  // ── Computed totals ──────────────────────────────────────────────────────────
  Map<String, int> get _projectTotals {
    final map = <String, int>{};
    for (final e in _entries) {
      final key = e.label.isNotEmpty ? e.label : '(no label)';
      map[key] = (map[key] ?? 0) + e.durationSecs;
    }
    return Map.fromEntries(map.entries.toList()..sort((a, b) => b.value.compareTo(a.value)));
  }

  int get _grandTotal => _entries.fold(0, (s, e) => s + e.durationSecs);

  // ── Pull hours PDF ───────────────────────────────────────────────────────────
  Future<void> _showPullHours() async {
    final totals   = _projectTotals;
    final selected = <String>{...totals.keys};  // all selected by default

    await showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: const Color(0xFF16213E),
      shape: const RoundedRectangleBorder(borderRadius: BorderRadius.vertical(top: Radius.circular(16))),
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setSheet) {
          final filteredEntries = _entries.where((e) {
            final k = e.label.isNotEmpty ? e.label : '(no label)';
            return selected.contains(k);
          }).toList();
          final filteredTotal = filteredEntries.fold(0, (s, e) => s + e.durationSecs);

          return Padding(
            padding: EdgeInsets.fromLTRB(24, 24, 24, MediaQuery.of(ctx).viewInsets.bottom + 24),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                const Text('Pull Hours', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: Color(0xFFEAEAEA))),
                const SizedBox(height: 12),

                // Project toggles
                ...totals.entries.map((kv) => CheckboxListTile(
                  contentPadding: EdgeInsets.zero,
                  value: selected.contains(kv.key),
                  activeColor: const Color(0xFFE94560),
                  title: Text(kv.key, style: const TextStyle(color: Color(0xFFEAEAEA))),
                  subtitle: Text(_fmtHours(kv.value), style: const TextStyle(color: Color(0xFF8A8AA0))),
                  onChanged: (v) => setSheet(() {
                    if (v == true) selected.add(kv.key); else selected.remove(kv.key);
                  }),
                )),

                const Divider(color: Color(0xFF0F3460)),
                Padding(
                  padding: const EdgeInsets.symmetric(vertical: 4),
                  child: Text('Total: ${_fmtHours(filteredTotal)}  (${(filteredTotal / 3600).toStringAsFixed(2)} hrs)',
                      style: const TextStyle(color: Color(0xFFEAEAEA), fontWeight: FontWeight.bold)),
                ),
                const SizedBox(height: 12),

                ElevatedButton.icon(
                  icon: const Icon(Icons.picture_as_pdf),
                  label: const Text('Generate PDF'),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: const Color(0xFFE94560),
                    padding: const EdgeInsets.symmetric(vertical: 14),
                  ),
                  onPressed: selected.isEmpty ? null : () async {
                    Navigator.pop(ctx);
                    await _generatePdf(filteredEntries, filteredTotal);
                  },
                ),
              ],
            ),
          );
        },
      ),
    );
  }

  Future<void> _generatePdf(List<Entry> entries, int totalSecs) async {
    final doc = pw.Document();
    final now = DateTime.now();
    final title = 'Time Report — ${now.toIso8601String().substring(0, 10)}';

    doc.addPage(pw.MultiPage(
      pageFormat: PdfPageFormat.a4,
      margin: const pw.EdgeInsets.all(40),
      build: (ctx) => [
        pw.Text(title, style: pw.TextStyle(fontSize: 18, fontWeight: pw.FontWeight.bold)),
        pw.SizedBox(height: 12),
        pw.TableHelper.fromTextArray(
          headers: ['Date', 'Start', 'End', 'Duration', 'Label', 'Comment'],
          headerStyle: pw.TextStyle(fontWeight: pw.FontWeight.bold, fontSize: 9),
          cellStyle: const pw.TextStyle(fontSize: 8),
          data: entries.map((e) => [
            e.date, e.startTime, e.endTime, e.durationStr,
            e.label, e.comment,
          ]).toList(),
        ),
        pw.SizedBox(height: 12),
        pw.Text(
          'Total: ${entries.length} sessions  •  ${_fmtHours(totalSecs)}  •  ${(totalSecs / 3600).toStringAsFixed(2)} hrs',
          style: pw.TextStyle(fontWeight: pw.FontWeight.bold),
        ),
      ],
    ));

    await Printing.layoutPdf(onLayout: (_) async => doc.save());
  }

  // ── Delete entry ─────────────────────────────────────────────────────────────
  Future<void> _delete(Entry e) async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (_) => AlertDialog(
        backgroundColor: const Color(0xFF16213E),
        title: const Text('Delete Entry'),
        content: const Text('Delete this time entry?'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Cancel')),
          TextButton(onPressed: () => Navigator.pop(context, true),  child: const Text('Delete', style: TextStyle(color: Color(0xFFE74C3C)))),
        ],
      ),
    );
    if (ok == true && e.id != null) {
      await DbService.deleteEntry(e.id!);
      SyncService.deleteEntry(e.syncId);
      _load();
    }
  }

  // ── Add entry ────────────────────────────────────────────────────────────────
  Future<void> _showAddEntryDialog() async {
    DateTime startDate   = DateTime.now();
    DateTime endDate     = DateTime.now();
    TimeOfDay startTime  = const TimeOfDay(hour: 9, minute: 0);
    TimeOfDay endTime    = const TimeOfDay(hour: 10, minute: 0);
    bool sameDay         = true;
    Color selectedColor  = _palette[0];
    final labelCtrl      = TextEditingController();
    final commentCtrl    = TextEditingController();

    await showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: const Color(0xFF16213E),
      shape: const RoundedRectangleBorder(borderRadius: BorderRadius.vertical(top: Radius.circular(16))),
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setSheet) {
          String fmtDate(DateTime d) => d.toIso8601String().substring(0, 10);

          return Padding(
            padding: EdgeInsets.fromLTRB(24, 24, 24, MediaQuery.of(ctx).viewInsets.bottom + 24),
            child: SingleChildScrollView(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  const Text('Add Entry', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: Color(0xFFEAEAEA))),
                  const SizedBox(height: 16),

                  // Start date + time
                  Row(children: [
                    Expanded(child: ListTile(
                      contentPadding: EdgeInsets.zero,
                      title: Text('Start: ${fmtDate(startDate)}', style: const TextStyle(color: Color(0xFFEAEAEA), fontSize: 13)),
                      trailing: const Icon(Icons.calendar_today, color: Color(0xFF8A8AA0), size: 18),
                      onTap: () async {
                        final d = await showDatePicker(context: ctx, initialDate: startDate,
                            firstDate: DateTime(2020), lastDate: DateTime.now().add(const Duration(days: 1)));
                        if (d != null) setSheet(() { startDate = d; if (sameDay) endDate = d; });
                      },
                    )),
                    Expanded(child: ListTile(
                      contentPadding: EdgeInsets.zero,
                      title: Text(startTime.format(ctx), style: const TextStyle(color: Color(0xFFEAEAEA), fontSize: 13)),
                      trailing: const Icon(Icons.access_time, color: Color(0xFF8A8AA0), size: 18),
                      onTap: () async {
                        final t = await showTimePicker(context: ctx, initialTime: startTime);
                        if (t != null) setSheet(() => startTime = t);
                      },
                    )),
                  ]),

                  Row(children: [
                    Checkbox(value: sameDay, activeColor: const Color(0xFFE94560),
                        onChanged: (v) => setSheet(() { sameDay = v ?? true; if (sameDay) endDate = startDate; })),
                    const Text('Same day', style: TextStyle(color: Color(0xFFEAEAEA))),
                  ]),

                  // End date + time
                  Row(children: [
                    Expanded(child: ListTile(
                      contentPadding: EdgeInsets.zero,
                      title: Text('End: ${fmtDate(endDate)}',
                          style: TextStyle(color: sameDay ? const Color(0xFF555570) : const Color(0xFFEAEAEA), fontSize: 13)),
                      trailing: Icon(Icons.calendar_today, color: sameDay ? const Color(0xFF555570) : const Color(0xFF8A8AA0), size: 18),
                      onTap: sameDay ? null : () async {
                        final d = await showDatePicker(context: ctx, initialDate: endDate,
                            firstDate: startDate, lastDate: startDate.add(const Duration(days: 2)));
                        if (d != null) setSheet(() => endDate = d);
                      },
                    )),
                    Expanded(child: ListTile(
                      contentPadding: EdgeInsets.zero,
                      title: Text(endTime.format(ctx), style: const TextStyle(color: Color(0xFFEAEAEA), fontSize: 13)),
                      trailing: const Icon(Icons.access_time_filled, color: Color(0xFF8A8AA0), size: 18),
                      onTap: () async {
                        final t = await showTimePicker(context: ctx, initialTime: endTime);
                        if (t != null) setSheet(() => endTime = t);
                      },
                    )),
                  ]),

                  const SizedBox(height: 8),
                  TextField(controller: labelCtrl,
                      decoration: const InputDecoration(labelText: 'Project / Client', labelStyle: TextStyle(color: Color(0xFF8A8AA0))),
                      style: const TextStyle(color: Colors.white)),
                  const SizedBox(height: 8),
                  TextField(controller: commentCtrl,
                      decoration: const InputDecoration(labelText: 'Comment', labelStyle: TextStyle(color: Color(0xFF8A8AA0))),
                      style: const TextStyle(color: Colors.white)),
                  const SizedBox(height: 12),

                  // Color picker
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceEvenly,
                    children: _palette.map((c) {
                      final sel = c == selectedColor;
                      return GestureDetector(
                        onTap: () => setSheet(() => selectedColor = c),
                        child: AnimatedContainer(
                          duration: const Duration(milliseconds: 150),
                          width: sel ? 30 : 24, height: sel ? 30 : 24,
                          decoration: BoxDecoration(
                            color: c, shape: BoxShape.circle,
                            border: sel ? Border.all(color: Colors.white, width: 2.5) : null,
                            boxShadow: sel ? [BoxShadow(color: c.withOpacity(0.6), blurRadius: 8)] : null,
                          ),
                        ),
                      );
                    }).toList(),
                  ),
                  const SizedBox(height: 20),

                  ElevatedButton(
                    style: ElevatedButton.styleFrom(backgroundColor: const Color(0xFFE94560), padding: const EdgeInsets.symmetric(vertical: 14)),
                    onPressed: () async {
                      final startDt = DateTime(startDate.year, startDate.month, startDate.day, startTime.hour, startTime.minute);
                      final endDt   = DateTime(endDate.year, endDate.month, endDate.day, endTime.hour, endTime.minute);
                      final secs    = endDt.difference(startDt).inSeconds;
                      if (secs <= 0) {
                        ScaffoldMessenger.of(ctx).showSnackBar(const SnackBar(content: Text('End must be after start')));
                        return;
                      }
                      final h = secs ~/ 3600; final m = (secs % 3600) ~/ 60; final s = secs % 60;
                      final durStr = '${h.toString().padLeft(2,'0')}:${m.toString().padLeft(2,'0')}:${s.toString().padLeft(2,'0')}';
                      final colorHex = '#${selectedColor.red.toRadixString(16).padLeft(2,'0')}'
                                       '${selectedColor.green.toRadixString(16).padLeft(2,'0')}'
                                       '${selectedColor.blue.toRadixString(16).padLeft(2,'0')}';
                      final entry = Entry(
                        syncId: const Uuid().v4(),
                        date: startDate.toIso8601String().substring(0, 10),
                        startTime: '${startTime.hour.toString().padLeft(2,'0')}:${startTime.minute.toString().padLeft(2,'0')}:00',
                        endTime:   '${endTime.hour.toString().padLeft(2,'0')}:${endTime.minute.toString().padLeft(2,'0')}:00',
                        durationSecs: secs, durationStr: durStr,
                        label: labelCtrl.text.trim(), tagColor: colorHex, comment: commentCtrl.text.trim(),
                      );
                      await DbService.insertEntry(entry);
                      SyncService.pushEntry(entry);
                      if (ctx.mounted) Navigator.pop(ctx);
                      _load();
                    },
                    child: const Text('Save Entry', style: TextStyle(fontWeight: FontWeight.bold)),
                  ),
                ],
              ),
            ),
          );
        },
      ),
    );

    labelCtrl.dispose();
    commentCtrl.dispose();
  }

  // ── Build ────────────────────────────────────────────────────────────────────
  @override
  Widget build(BuildContext context) {
    final totals = _projectTotals;
    final grand  = _grandTotal;

    return Scaffold(
      appBar: AppBar(
        title: const Text('TIME LOG'),
        leading: BackButton(onPressed: () => context.pop()),
        actions: [
          IconButton(icon: const Icon(Icons.summarize), tooltip: 'Pull Hours', onPressed: _showPullHours),
          IconButton(icon: const Icon(Icons.home), tooltip: 'Home', onPressed: () => context.go('/')),
        ],
      ),
      floatingActionButton: FloatingActionButton(
        onPressed: _showAddEntryDialog,
        backgroundColor: const Color(0xFFE94560),
        child: const Icon(Icons.add),
      ),
      body: _entries.isEmpty
          ? const Center(child: Text('No entries yet.', style: TextStyle(color: Color(0xFF8A8AA0))))
          : Column(
              children: [
                // ── Project totals summary ──
                Container(
                  color: const Color(0xFF0F3460),
                  padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      ...totals.entries.map((kv) {
                        // Find representative color for this label
                        final match = _entries.firstWhere(
                          (e) => (e.label.isNotEmpty ? e.label : '(no label)') == kv.key && e.tagColor.isNotEmpty,
                          orElse: () => _entries.first,
                        );
                        final color = _parseHex(match.tagColor);
                        return Padding(
                          padding: const EdgeInsets.symmetric(vertical: 2),
                          child: Row(children: [
                            Container(width: 10, height: 10, decoration: BoxDecoration(color: color, shape: BoxShape.circle)),
                            const SizedBox(width: 8),
                            Expanded(child: Text(kv.key, style: const TextStyle(color: Color(0xFFEAEAEA), fontSize: 12))),
                            Text(_fmtHours(kv.value), style: const TextStyle(color: Color(0xFF8A8AA0), fontSize: 12)),
                          ]),
                        );
                      }),
                      const Divider(color: Color(0xFF16213E), height: 10),
                      Row(children: [
                        const Expanded(child: Text('TOTAL', style: TextStyle(color: Color(0xFFEAEAEA), fontSize: 12, fontWeight: FontWeight.bold))),
                        Text(_fmtHours(grand), style: const TextStyle(color: Color(0xFFE94560), fontSize: 12, fontWeight: FontWeight.bold)),
                      ]),
                    ],
                  ),
                ),

                // ── Entry list ──
                Expanded(
                  child: ListView.separated(
                    itemCount: _entries.length,
                    separatorBuilder: (_, __) => const Divider(height: 1, color: Color(0xFF0F3460)),
                    itemBuilder: (_, i) {
                      final e = _entries[i];
                      final tagColor = _parseHex(e.tagColor);
                      return Container(
                        color: const Color(0xFF16213E),
                        child: Row(children: [
                          // Color bar
                          Container(width: 4, height: 56, color: tagColor),
                          Expanded(
                            child: ListTile(
                              title: Text(
                                '${e.date}  ${e.startTime} – ${e.endTime}  (${e.durationStr})',
                                style: const TextStyle(color: Color(0xFFEAEAEA), fontSize: 13),
                              ),
                              subtitle: e.label.isNotEmpty || e.comment.isNotEmpty
                                  ? Text('${e.label}${e.comment.isNotEmpty ? "  •  ${e.comment}" : ""}',
                                      style: TextStyle(color: tagColor.withOpacity(0.85), fontSize: 12))
                                  : null,
                              trailing: IconButton(
                                icon: const Icon(Icons.delete_outline, color: Color(0xFF8A8AA0)),
                                onPressed: () => _delete(e),
                              ),
                            ),
                          ),
                        ]),
                      );
                    },
                  ),
                ),
              ],
            ),
    );
  }
}
