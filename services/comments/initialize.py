"""Initialize the pinned schema before serving the empty pilot."""
import sqlite3
from isso import config, make_app

conf = config.load(config.default_file(), '/etc/humanstories-isso.cfg')
app = make_app(conf)
with sqlite3.connect(conf.get('general', 'dbpath')) as db:
    sql = db.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='comments'").fetchone()[0]
    if 'AUTOINCREMENT' not in sql.upper():
        if db.execute('SELECT COUNT(*) FROM comments').fetchone()[0]:
            raise RuntimeError('Refusing schema migration on a nonempty pilot database.')
        db.execute('DROP TABLE comments')
        db.execute(sql.replace('INTEGER PRIMARY KEY', 'INTEGER PRIMARY KEY AUTOINCREMENT'))
    db.execute('CREATE TABLE IF NOT EXISTS pilot_removals (id INTEGER PRIMARY KEY, created REAL, removed_at TEXT NOT NULL, reason TEXT)')
    db.executescript('''
    CREATE TRIGGER IF NOT EXISTS pilot_no_edit BEFORE UPDATE ON comments
    WHEN NEW.mode != 4 AND (NEW.text IS NOT OLD.text OR NEW.author IS NOT OLD.author OR NEW.website IS NOT OLD.website)
    BEGIN SELECT RAISE(ABORT, 'Comments are immutable; reply or remove instead.'); END;
    CREATE TRIGGER IF NOT EXISTS pilot_deleted AFTER DELETE ON comments
    BEGIN INSERT OR IGNORE INTO pilot_removals(id,created,removed_at) VALUES(OLD.id,OLD.created,datetime('now')); END;
    CREATE TRIGGER IF NOT EXISTS pilot_removed AFTER UPDATE OF mode ON comments
    WHEN NEW.mode=4 AND OLD.mode!=4
    BEGIN INSERT OR IGNORE INTO pilot_removals(id,created,removed_at) VALUES(OLD.id,OLD.created,datetime('now')); END;
    ''')
print('Stable IDs, immutable text, and removal ledger initialized.')
