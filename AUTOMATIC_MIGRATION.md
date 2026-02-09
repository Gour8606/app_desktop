# Automatic Database Migration System

**Created:** November 22, 2025

## Overview

The application now includes an **automatic database migration system** that runs on startup. You never need to manually run migration scripts or worry about database schema changes.

## Key Features

### ✅ Fully Automatic
- Runs every time you start the application
- No manual intervention required
- Safe to run multiple times (idempotent)

### ✅ Handles Everything
- Creates missing tables
- Adds missing columns to existing tables
- Creates indexes for performance
- Verifies multi-seller setup

### ✅ Database Recovery
**If you delete the database file (`meesho_sales.db`):**
1. Just restart the application
2. All tables will be recreated automatically
3. Import your data again
4. Everything works!

## How It Works

### Startup Sequence

When you run `python main.py`:

```
1. Import modules
2. Run initialize_database()
   ├── Auto-migrate schema
   │   ├── Check existing tables
   │   ├── Create missing tables
   │   ├── Add missing columns
   │   └── Create missing indexes
   └── Verify multi-seller setup
       ├── Check seller mappings
       ├── Check inventory GSTIN tagging
       └── Check payment GSTIN tagging
3. Launch GUI
```

### What Gets Created

#### Tables
- `seller_mapping` - Supplier ID → GSTIN mapping
- `meesho_sales` - GST invoice data
- `meesho_returns` - GST return data
- `meesho_inventory` - Product inventory
- `meesho_payments` - Payment details
- `meesho_ads_cost` - Advertising costs
- `flipkart_orders` - Flipkart sales
- `flipkart_returns` - Flipkart returns
- `amazon_orders` - Amazon sales
- `amazon_returns` - Amazon returns
- ... and all other tables

#### Multi-Seller Columns
Automatically adds `seller_gstin` column to:
- `meesho_inventory`
- `meesho_payments`
- `meesho_ads_cost`
- `meesho_referral_payments`
- `meesho_compensation_recovery`
- `flipkart_orders`
- `flipkart_returns`
- `amazon_orders`
- `amazon_returns`

#### Indexes
Creates indexes on `seller_gstin` columns for fast filtering.

## Console Output Example

```
============================================================
DATABASE INITIALIZATION
============================================================
✅ Database schema is up-to-date
📋 Creating index on amazon_orders.seller_gstin
✅ Created index: ix_amazon_orders_seller_gstin

Multi-Seller Setup Status:
✅ 3 seller mapping(s) configured
⚠️  Inventory: 1377 records need GSTIN tagging (re-import required)
⚠️  Payments: 16636 records need GSTIN tagging (re-import required)
============================================================
```

## What Happens on Fresh Start

### Scenario 1: Brand New Database (No File)
```
1. Application starts
2. Migration creates all tables
3. ✅ All tables created
4. ⚠️  No seller mappings found
5. GUI launches
6. Import GST data → Creates seller mappings
7. Import inventory/payments → Auto-tags with GSTIN
```

### Scenario 2: Deleted Database File
```
1. You delete meesho_sales.db
2. Application starts
3. Migration creates all tables with latest schema
4. ✅ All tables created with multi-seller support
5. GUI launches
6. Re-import your data
7. Everything works!
```

### Scenario 3: Old Database (Missing Columns)
```
1. Application starts with old database
2. Migration detects missing seller_gstin columns
3. 📋 Adding column seller_gstin to meesho_inventory
4. ✅ Added column: meesho_inventory.seller_gstin
5. Repeats for all tables
6. Creates indexes
7. ✅ Database upgraded
8. GUI launches
```

### Scenario 4: Up-to-Date Database
```
1. Application starts
2. Migration checks schema
3. ✅ Database schema is up-to-date
4. ✅ 3 seller mappings configured
5. ✅ All data properly tagged
6. GUI launches
```

## Files Involved

### Core Files
- **`auto_migrate.py`** - Migration logic
  - `auto_migrate()` - Main migration function
  - `verify_multi_seller_setup()` - Status checking
  - `get_table_columns()` - Schema inspection
  - `get_table_names()` - Table listing

- **`main.py`** - Integration point
  - `initialize_database()` - Runs on startup
  - Imports from `auto_migrate`

### Model Definitions
- **`models.py`** - SQLAlchemy models
  - Defines all table structures
  - Auto-migration uses these as reference

## Migration Logic

### Safe Column Addition
```python
# Checks if column exists before adding
existing_cols = get_table_columns(table_name)
if 'seller_gstin' not in existing_cols:
    ALTER TABLE meesho_inventory ADD COLUMN seller_gstin VARCHAR
```

### Safe Table Creation
```python
# Only creates tables that don't exist
if 'seller_mapping' not in existing_tables:
    Base.metadata.create_all(engine)
```

### Safe Index Creation
```python
# Checks if index exists before creating
if 'ix_meesho_inventory_seller_gstin' not in index_names:
    CREATE INDEX ix_meesho_inventory_seller_gstin ON meesho_inventory (seller_gstin)
```

## Manual Migration (If Needed)

Although automatic migration runs on startup, you can also run it manually:

```powershell
# Test migration without starting GUI
python auto_migrate.py
```

This is useful for:
- Testing schema changes
- Debugging migration issues
- Checking database status

## Status Messages

### ✅ Success Messages
- `✅ Database schema is up-to-date` - No changes needed
- `✅ All tables created` - Fresh database initialized
- `✅ Added column: table_name.column_name` - Column added
- `✅ Created index: index_name` - Index created
- `✅ N seller mappings configured` - Mappings exist
- `✅ All N records have GSTIN` - Data properly tagged

### ⚠️ Warning Messages
- `⚠️ No seller mappings found` - Import GST data first
- `⚠️ N records need GSTIN tagging` - Re-import required
- `⚠️ Column may already exist` - Safe duplicate attempt
- `⚠️ Index may already exist` - Safe duplicate attempt

### ❌ Error Messages
- `❌ Migration error: ...` - Something went wrong (rare)

## Best Practices

### For Normal Use
1. **Just start the app** - Migration happens automatically
2. **Watch the console** - Check for warnings
3. **Import GST data first** - Creates seller mappings
4. **Then import inventory/payments** - Auto-tags with GSTIN

### For Development
1. **Modify `models.py`** - Add new tables/columns
2. **Update `auto_migrate.py`** - Add to expected_schema
3. **Test with `python auto_migrate.py`** - Verify changes
4. **Start app** - Changes apply automatically

### For Data Recovery
1. **Backup `meesho_sales.db`** - Before major changes
2. **If database corrupted** - Delete and restart app
3. **Re-import data** - All schema is auto-created
4. **Everything works** - No manual steps needed

## Advantages Over Manual Migration

| Manual Migration | Automatic Migration |
|------------------|---------------------|
| Run script before starting app | Runs on app startup |
| Remember to run after updates | Always runs automatically |
| Can forget to run | Never forget |
| Manual intervention | Zero intervention |
| Error-prone | Reliable |
| User needs to know SQL | No SQL knowledge needed |

## Technical Details

### SQLAlchemy Integration
- Uses SQLAlchemy's `inspect` module to check schema
- Uses `Base.metadata` to create tables
- Raw SQL for column/index additions (more reliable)

### Idempotent Operations
Every operation checks before executing:
- Table exists? Don't create
- Column exists? Don't add
- Index exists? Don't create

### Error Handling
- Catches exceptions on column/index creation
- Reports issues but doesn't crash
- Continues with remaining migrations

### Performance
- Fast schema checks (<1 second)
- Only runs DDL when needed
- Indexed queries for status verification

## Future Enhancements

Potential additions:
- Data migration (transforming existing data)
- Version tracking (migration history)
- Rollback capability (undo changes)
- Cloud database support (PostgreSQL, MySQL)

## Troubleshooting

### "Column already exists" Error
**Harmless** - Migration tried to add existing column. Ignore the warning.

### "No seller mappings found"
**Action Required** - Import GST data to create mappings.

### "N records need GSTIN tagging"
**Action Required** - Re-import inventory/payment data with proper filenames.

### Migration Seems Stuck
**Rare** - Database might be locked. Close app, restart.

## Summary

**You never need to worry about database schema again!**

- ✅ Delete database? Just restart the app.
- ✅ Update code? Migration runs automatically.
- ✅ New developer? App sets up database on first run.
- ✅ Multiple machines? Same code works everywhere.

The automatic migration system ensures your database is always in sync with the code, with zero manual intervention required.
