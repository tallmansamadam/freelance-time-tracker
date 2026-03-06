class Entry {
  final int?    id;
  final String  syncId;
  final String  date;
  final String  startTime;
  final String  endTime;
  final int     durationSecs;
  final String  durationStr;
  final String  label;
  final String  tagColor;
  final String  comment;
  final bool    synced;

  const Entry({
    this.id,
    required this.syncId,
    required this.date,
    required this.startTime,
    required this.endTime,
    required this.durationSecs,
    required this.durationStr,
    required this.label,
    required this.tagColor,
    required this.comment,
    this.synced = false,
  });

  // Hours as decimal for billing calculations
  double get hours => durationSecs / 3600;

  factory Entry.fromMap(Map<String, dynamic> m) => Entry(
        id:           m['id'] as int?,
        syncId:       m['sync_id']       as String? ?? '',
        date:         m['date']          as String,
        startTime:    m['start_time']    as String,
        endTime:      m['end_time']      as String,
        durationSecs: m['duration_secs'] as int,
        durationStr:  m['duration_str']  as String,
        label:        m['label']         as String? ?? '',
        tagColor:     m['tag_color']     as String? ?? '',
        comment:      m['comment']       as String? ?? '',
        synced:       (m['synced'] as int? ?? 0) == 1,
      );

  Map<String, dynamic> toMap() => {
        if (id != null) 'id': id,
        'sync_id':       syncId,
        'date':          date,
        'start_time':    startTime,
        'end_time':      endTime,
        'duration_secs': durationSecs,
        'duration_str':  durationStr,
        'label':         label,
        'tag_color':     tagColor,
        'comment':       comment,
        'synced':        synced ? 1 : 0,
      };

  Map<String, dynamic> toSupabase() => {
        'sync_id':       syncId,
        'date':          date,
        'start_time':    startTime,
        'end_time':      endTime,
        'duration_secs': durationSecs,
        'duration_str':  durationStr,
        'label':         label,
        'tag_color':     tagColor,
        'comment':       comment,
      };
}
