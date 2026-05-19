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