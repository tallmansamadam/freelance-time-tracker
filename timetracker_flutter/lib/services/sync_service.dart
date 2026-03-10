import 'package:flutter/foundation.dart';
import 'package:supabase_flutter/supabase_flutter.dart';
import 'db_service.dart';
import '../models/entry.dart';

class SyncService {
  static final _client = Supabase.instance.client;

  /// Push a single entry (upsert). Call in background after any write.
  static Future<void> pushEntry(Entry entry) async {
    try {
      await _client
          .from('entries')
          .upsert(entry.toSupabase(), onConflict: 'sync_id');
      await DbService.markSynced(entry.syncId);
      debugPrint('[Sync] pushEntry OK: ${entry.syncId}');
    } catch (e) {
      debugPrint('[Sync] pushEntry FAILED: $e');
      // Offline — entry stays pending, will sync on next app launch
    }
  }

  /// Delete a remote entry by sync_id.
  static Future<void> deleteEntry(String syncId) async {
    try {
      await _client.from('entries').delete().eq('sync_id', syncId);
      debugPrint('[Sync] deleteEntry OK: $syncId');
    } catch (e) {
      debugPrint('[Sync] deleteEntry FAILED: $e');
    }
  }

  /// On startup: push all locally-saved rows that haven't been synced yet.
  static Future<void> pushPending() async {
    final pending = await DbService.pendingSync();
    debugPrint('[Sync] pushPending: ${pending.length} entries');
    for (final entry in pending) {
      await pushEntry(entry);
    }
  }

  /// On startup: pull all remote entries into local DB (offline-first merge).
  /// Uses INSERT OR IGNORE (via ConflictAlgorithm.ignore) so existing local
  /// rows are never overwritten — sync_id UNIQUE constraint prevents duplicates.
  static Future<void> pullEntries() async {
    try {
      final rows = await _client.from('entries').select();
      debugPrint('[Sync] pullEntries: ${rows.length} rows from Supabase');
      for (final row in rows) {
        final map = Map<String, dynamic>.from(row as Map);
        map.remove('id');
        map.remove('created_at');
        map['synced'] = 1;
        await DbService.insertEntryIgnore(Entry.fromMap(map));
      }
    } catch (e) {
      debugPrint('[Sync] pullEntries FAILED: $e');
    }
  }
}
