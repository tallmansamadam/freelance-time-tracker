import 'package:sqflite/sqflite.dart';
import 'package:path/path.dart' as p;
import '../models/entry.dart';

class DbService {
  static Database? _db;

  static Future<Database> get db async {
    _db ??= await _open();
    return _db!;
  }

  static Future<Database> _open() async {
    final dbPath = p.join(await getDatabasesPath(), 'timetracker.db');
    return openDatabase(
      dbPath,
      version: 1,
      onCreate: (db, _) async {
        await db.execute('''
          CREATE TABLE entries (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            sync_id       TEXT    UNIQUE NOT NULL,
            date          TEXT    NOT NULL,
            start_time    TEXT    NOT NULL,
            end_time      TEXT    NOT NULL,
            duration_secs INTEGER NOT NULL,
            duration_str  TEXT    NOT NULL,
            label         TEXT    DEFAULT '',
            tag_color     TEXT    DEFAULT '',
            comment       TEXT    DEFAULT '',
            synced        INTEGER DEFAULT 0
          )
        ''');
      },
    );
  }

  /// Insert a new entry; replace on sync_id conflict (local writes).
  static Future<int> insertEntry(Entry e) async {
    return (await db).insert('entries', e.toMap(),
        conflictAlgorithm: ConflictAlgorithm.replace);
  }

  /// Insert from a remote pull; ignore if sync_id already exists locally.
  static Future<void> insertEntryIgnore(Entry e) async {
    await (await db).insert('entries', e.toMap(),
        conflictAlgorithm: ConflictAlgorithm.ignore);
  }

  static Future<void> updateEntry(Entry e) async {
    await (await db).update('entries', e.toMap(),
        where: 'id = ?', whereArgs: [e.id]);
  }

  static Future<void> deleteEntry(int id) async {
    await (await db).delete('entries', where: 'id = ?', whereArgs: [id]);
  }

  static Future<List<Entry>> allEntries() async {
    final rows = await (await db).query('entries', orderBy: 'date DESC, start_time DESC');
    return rows.map(Entry.fromMap).toList();
  }

  static Future<List<Entry>> entriesByLabel(String label) async {
    final rows = await (await db).query('entries',
        where: 'label = ?', whereArgs: [label], orderBy: 'date ASC, start_time ASC');
    return rows.map(Entry.fromMap).toList();
  }

  static Future<List<String>> distinctLabels() async {
    final rows = await (await db).rawQuery(
      "SELECT DISTINCT label FROM entries WHERE label != '' ORDER BY label COLLATE NOCASE"
    );
    return rows.map((r) => r['label'] as String).toList();
  }

  static Future<List<Entry>> pendingSync() async {
    final rows = await (await db).query('entries',
        where: 'synced = 0 OR synced IS NULL');
    return rows.map(Entry.fromMap).toList();
  }

  static Future<void> markSynced(String syncId) async {
    await (await db).update('entries', {'synced': 1},
        where: 'sync_id = ?', whereArgs: [syncId]);
  }
}
