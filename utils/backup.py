import os
import shutil
from datetime import datetime

from utils.logger import logger


def make_backup(db_path="tsg_database.sql", backups="backups", ):
    os.makedirs(backups, exist_ok=True)
    now = datetime.now()
    date_str = now.strftime("%d-%m-%Y")
    backup_path = os.path.join(backups, f"backup_{date_str}.sql")
    shutil.copy2(db_path, backup_path)
    logger.info(f"[✓] Резервная копия создана: {backup_path}")

