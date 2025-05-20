#!/bin/bash
set -e  # Exit on any error

DATE=$(date +%Y%m%d)
DB_NAME="servicescheduler"
DB_USER="stipton"
SNAPSHOT_DIR="./db_snapshots"
SNAPSHOT_FILE="$SNAPSHOT_DIR/snapshot_$DATE.sql"
MIGRATION_FILE="$SNAPSHOT_DIR/migration_state_$DATE.txt"

echo "Creating snapshot directory..."
mkdir -p $SNAPSHOT_DIR

echo "Dumping database..."
if ! pg_dump -v -U $DB_USER $DB_NAME > "$SNAPSHOT_FILE" 2>&1; then
    echo "Error: Database dump failed!"
    exit 1
fi

echo "Checking if database dump was created..."
if [ ! -s "$SNAPSHOT_FILE" ]; then
    echo "Error: Database dump file is empty or was not created!"
    exit 1
fi

echo "Recording migration state..."
if ! python manage.py showmigrations > "$MIGRATION_FILE" 2>&1; then
    echo "Error: Failed to record migration state!"
    exit 1
fi

echo "Checking if migration state file was created..."
if [ ! -s "$MIGRATION_FILE" ]; then
    echo "Error: Migration state file is empty or was not created!"
    exit 1
fi

echo "Snapshot created successfully for $DATE"
echo "Files created:"
echo "- Database dump: $SNAPSHOT_FILE"
echo "- Migration state: $MIGRATION_FILE"


# To restore from snapshot from the following command:
# psql -U postgres servicescheduler < db_snapshots/snapshot_20250414.sql

# To fake migrations up to the point of this snapshot:
# Only do this if you know the schema is already in the state implied by migrations. 
# (Which is true because it's from a snapshot you created from a working state.)
# python manage.py migrate --fake


# To apply newer migrations:
# python manage.py migrate
