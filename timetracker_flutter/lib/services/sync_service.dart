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
    } catch (_) {
      // Offline — entry stays pending, will sync on next app launch
    }
  }

  /// Delete a remote entry by sync_id.
  static Future<void> deleteEntry(String syncId) async {
    try {
      await _client.from('entries').delete().eq('sync_id', syncId);
    } catch (_) {}
  }

  /// On startup: push all locally-saved rows that haven't been synced yet.
  static Future<void> pushPending() async {
    final pending = await DbService.pendingSync();
    for (final entry in pending) {
      await pushEntry(entry);
    }
  }
}
