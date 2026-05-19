cp -r data data_backup_$(date +%Y%m%d_%H%M%S)
# 1 
# db.py
# python3 -c "from db import init_db; init_db(); print('DB OK')"



(QUIZ) adam@mac QuizApp % python3 migrate_json_to_sqlite.py
Users migrated: 2
Topics migrated: 3
Questions migrated: 662
History migrated: 213
Migration completed.



python3 - <<'PY'
from db import get_db

with get_db() as db:
    for table in ["users", "topics", "questions", "results", "history"]:
        count = db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(table, count)
PY



(QUIZ) adam@mac QuizApp % python3 - <<'PY'
from db import get_db

with get_db() as db:
    for table in ["users", "topics", "questions", "results", "history"]:
        count = db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(table, count)
PY
users 5
topics 3
questions 662
results 11
history 213