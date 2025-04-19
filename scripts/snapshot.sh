#!/bin/bash
DATE=$(date +%Y%m%d)
DB_NAME="servicescheduler"
DB_USER="stipton"
SNAPSHOT_DIR="./db_snapshots"

mkdir -p $SNAPSHOT_DIR
pg_dump -U $DB_USER $DB_NAME > "$SNAPSHOT_DIR/snapshot_$DATE.sql"
python manage.py showmigrations > "$SNAPSHOT_DIR/migration_state_$DATE.txt"
echo "Snapshot created for $DATE"


# To restore from snapshot from the following command:
# psql -U postgres servicescheduler < db_snapshots/snapshot_20250414.sql

# To fake migrations up to the point of this snapshot:
# Only do this if you know the schema is already in the state implied by migrations. 
# (Which is true because it's from a snapshot you created from a working state.)
# python manage.py migrate --fake


# To apply newer migrations:
# python manage.py migrate
