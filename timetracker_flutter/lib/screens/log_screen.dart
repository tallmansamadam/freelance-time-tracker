import 'package:flutter/material.dart';
import '../models/entry.dart';
import '../services/db_service.dart';
import '../services/sync_service.dart';

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

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('TIME LOG'),
        leading: BackButton(onPressed: () => Navigator.pop(context)),
      ),
      body: _entries.isEmpty
          ? const Center(child: Text('No entries yet.', style: TextStyle(color: Color(0xFF8A8AA0))))
          : ListView.separated(
              itemCount: _entries.length,
              separatorBuilder: (_, __) =>
                  const Divider(height: 1, color: Color(0xFF0F3460)),
              itemBuilder: (_, i) {
                final e = _entries[i];
                return ListTile(
                  tileColor: const Color(0xFF16213E),
                  title: Text(
                    '${e.date}  ${e.startTime} – ${e.endTime}  (${e.durationStr})',
                    style: const TextStyle(color: Color(0xFFEAEAEA), fontSize: 13),
                  ),
                  subtitle: e.label.isNotEmpty || e.comment.isNotEmpty
                      ? Text('${e.label}  ${e.comment}',
                          style: const TextStyle(color: Color(0xFF8A8AA0), fontSize: 12))
                      : null,
                  trailing: IconButton(
                    icon: const Icon(Icons.delete_outline, color: Color(0xFF8A8AA0)),
                    onPressed: () => _delete(e),
                  ),
                );
              },
            ),
    );
  }
}
