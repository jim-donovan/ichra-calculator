#!/bin/bash
# Daily backup of ichra_data to Cloudflare R2
#
# Setup:
# 1. Create R2 bucket named 'ichra-backups' in Cloudflare Dashboard
# 2. Create R2 API token with read/write access
# 3. Configure AWS CLI: aws configure --profile r2
# 4. Update .env with your settings
# 5. Make executable: chmod +x backup_ichra_data.sh
# 6. Add to crontab: crontab -e
#    0 2 * * * /Users/jimdonovan/Desktop/GLOVE/ichra_calculator_v2/backup_ichra_data.sh >> /Users/jimdonovan/backups/ichra/backup.log 2>&1

# ============================================================
# Load configuration from .env
# ============================================================
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${SCRIPT_DIR}/.env"

if [ -f "$ENV_FILE" ]; then
    source "$ENV_FILE"
else
    echo "ERROR: .env not found at $ENV_FILE"
    exit 1
fi

# Build R2 endpoint
R2_ENDPOINT="https://${R2_ACCOUNT_ID}.r2.cloudflarestorage.com"

# Email recipient
NOTIFY_EMAIL="jim@jimdonovansolutions.com"

# ============================================================
# Email notification function
# ============================================================
send_email() {
    local subject="$1"
    local body="$2"

    if [ -z "$SENDGRID_API_KEY" ]; then
        echo "WARNING: SENDGRID_API_KEY not set, skipping email notification"
        return
    fi

    curl -s --request POST \
        --url https://api.sendgrid.com/v3/mail/send \
        --header "Authorization: Bearer $SENDGRID_API_KEY" \
        --header "Content-Type: application/json" \
        --data "{
            \"personalizations\": [{\"to\": [{\"email\": \"$NOTIFY_EMAIL\"}]}],
            \"from\": {\"email\": \"${SENDER_EMAIL:-noreply@glovesolutions.com}\", \"name\": \"${SENDER_NAME:-ICHRA Backup}\"},
            \"subject\": \"$subject\",
            \"content\": [{\"type\": \"text/plain\", \"value\": \"$body\"}]
        }" > /dev/null
}

# ============================================================
# Error handler
# ============================================================
ERROR_MSG=""
handle_error() {
    ERROR_MSG="$1"
    echo "ERROR: $ERROR_MSG"
    send_email "ICHRA Backup FAILED" "Backup failed at $(date)

Error: $ERROR_MSG

Check the log at: /Users/jimdonovan/backups/ichra/backup.log"
    exit 1
}

# ============================================================
# Script
# ============================================================

echo "============================================================"
echo "ICHRA Database Backup - $(date)"
echo "============================================================"

# Create backup directory if needed
mkdir -p "$BACKUP_DIR" || handle_error "Failed to create backup directory"

# Generate filename with timestamp
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
FILENAME="ichra_data_${TIMESTAMP}.sql.gz"
FILEPATH="${BACKUP_DIR}/${FILENAME}"

# Create compressed backup
echo "Creating backup: $FILENAME"
/opt/homebrew/opt/postgresql@17/bin/pg_dump "$DB_NAME" 2>&1 | gzip > "$FILEPATH"
if [ ${PIPESTATUS[0]} -ne 0 ]; then
    handle_error "pg_dump failed"
fi

SIZE=$(ls -lh "$FILEPATH" | awk '{print $5}')
echo "  -> Created: $FILEPATH ($SIZE)"

# Verify backup is not empty (should be at least 1MB for this database)
SIZE_BYTES=$(stat -f%z "$FILEPATH" 2>/dev/null || stat -c%s "$FILEPATH" 2>/dev/null)
if [ "$SIZE_BYTES" -lt 1000000 ]; then
    handle_error "Backup file too small ($SIZE) - possible pg_dump failure"
fi

# Upload to R2
if [ -n "$R2_ACCOUNT_ID" ] && [ -n "$R2_BUCKET" ]; then
    echo "Uploading to Cloudflare R2..."
    if ! aws s3 cp "$FILEPATH" "s3://${R2_BUCKET}/${FILENAME}" \
        --endpoint-url "$R2_ENDPOINT" \
        --profile r2 2>&1; then
        handle_error "R2 upload failed"
    fi
    echo "  -> Uploaded to R2: s3://${R2_BUCKET}/${FILENAME}"
else
    handle_error "R2 not configured (missing R2_ACCOUNT_ID or R2_BUCKET)"
fi

# Clean up old local backups
echo "Cleaning up local backups older than $LOCAL_RETENTION_DAYS days..."
DELETED=$(find "$BACKUP_DIR" -name "ichra_data_*.sql.gz" -mtime +$LOCAL_RETENTION_DAYS -delete -print | wc -l)
echo "  -> Deleted $DELETED old backup(s)"

echo ""
echo "Backup complete!"
echo "============================================================"

# Send success email
send_email "ICHRA Backup SUCCESS" "Backup completed successfully at $(date)

File: $FILENAME
Size: $SIZE
Location: s3://${R2_BUCKET}/${FILENAME}

Local backups cleaned: $DELETED file(s) older than $LOCAL_RETENTION_DAYS days"
