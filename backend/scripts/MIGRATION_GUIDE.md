# Supabase Migration Guide

This guide walks you through migrating the 2nd Brain database from Render PostgreSQL to Supabase.

## Prerequisites

- Python 3.9+
- Access to Render Dashboard
- Access to Supabase Dashboard

## Step 1: Get Your Database URLs

### Render Database URL
1. Go to https://dashboard.render.com
2. Click on your PostgreSQL database (dpg-d5smrdk9c44c739detag-a)
3. Copy the **External Database URL** (looks like `postgresql://user:pass@host:5432/db`)

### Supabase Database URL
1. Go to https://supabase.com/dashboard/project/bfsxwptbfuwhvazzyfbo/settings/database
2. Scroll down to **Connection string**
3. Click the **URI** tab
4. Copy the connection string
5. Replace `[YOUR-PASSWORD]` with your actual database password

Your Supabase URL will look like:
```
postgresql://postgres:YOUR_PASSWORD@db.bfsxwptbfuwhvazzyfbo.supabase.co:5432/postgres
```

## Step 2: Set Environment Variables

```bash
# Set the source (Render) database
export RENDER_DATABASE_URL="postgresql://user:pass@your-render-host:5432/secondbrain"

# Set the target (Supabase) database
export SUPABASE_DATABASE_URL="postgresql://postgres:YOUR_PASSWORD@db.bfsxwptbfuwhvazzyfbo.supabase.co:5432/postgres"
```

## Step 3: Run the Migration Script

```bash
cd backend
python scripts/migrate_to_supabase.py
```

The script will:
1. Export all data from Render (creates a backup JSON file)
2. Create tables in Supabase
3. Import all data to Supabase
4. Apply Row Level Security (RLS) policies

## Step 4: Apply RLS Policies (Optional - if script failed)

If the RLS policies weren't applied automatically:

1. Go to https://supabase.com/dashboard/project/bfsxwptbfuwhvazzyfbo/sql/new
2. Copy the contents of `scripts/supabase_rls_policies.sql`
3. Paste and run in the SQL Editor

## Step 5: Update Render Environment Variables

1. Go to https://dashboard.render.com
2. Click on your web service
3. Go to **Environment**
4. Update these variables:

```
DATABASE_URL=postgresql://postgres:YOUR_PASSWORD@db.bfsxwptbfuwhvazzyfbo.supabase.co:5432/postgres
SUPABASE_URL=https://bfsxwptbfuwhvazzyfbo.supabase.co
SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
SUPABASE_SERVICE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

5. Click **Save Changes** - this will trigger a redeploy

## Step 6: Verify Migration

1. Wait for Render to redeploy
2. Visit your application
3. Log in and verify:
   - User authentication works
   - Documents are visible
   - Integrations show correct status
   - Chat history is preserved

## Troubleshooting

### Connection Refused
If you get "connection refused" errors:
- Make sure you're using the **direct** connection string, not the pooler
- Check that your password doesn't contain special characters that need escaping

### Tables Not Found
If tables aren't created:
```bash
cd backend
python -c "from database.models import init_database; init_database()"
```

### RLS Blocking Queries
If queries return empty results after migration:
- The service_role key bypasses RLS
- Make sure your backend is using `SUPABASE_SERVICE_KEY`
- Verify the key is correctly set in Render environment

### Data Not Migrated
Check the backup JSON file created during migration:
```
backend/scripts/migration_backup_YYYYMMDD_HHMMSS.json
```

You can manually import this data if needed.

## Architecture Notes

### Row Level Security (RLS)
All tables have RLS enabled with tenant isolation:
- Queries are automatically filtered by `tenant_id`
- The `auth.tenant_id()` function extracts tenant from session
- Service role (backend) bypasses RLS for full access

### Connection Pooling
Supabase provides two connection endpoints:
- **Direct** (port 5432): For migrations and admin tasks
- **Pooler** (port 6543): For application connections (recommended)

For production, consider using the pooler connection string.

## Rollback

If you need to rollback to Render:
1. Update `DATABASE_URL` back to the Render URL
2. Redeploy on Render

Your original Render database is untouched by this migration.
