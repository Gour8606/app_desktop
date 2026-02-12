"""
Automatic database migration system
Runs on app startup to ensure database schema is up-to-date
"""
from sqlalchemy import inspect, text
from database import engine, SessionLocal
from models import Base
import logging

logger = logging.getLogger(__name__)

def get_table_columns(table_name: str) -> set:
    """Get list of column names for a table"""
    inspector = inspect(engine)
    if not inspector.has_table(table_name):
        return set()
    columns = inspector.get_columns(table_name)
    return {col['name'] for col in columns}

def get_table_names() -> set:
    """Get list of all table names in database"""
    inspector = inspect(engine)
    return set(inspector.get_table_names())

def auto_migrate():
    """
    Automatically migrate database schema to match models.
    - Creates missing tables
    - Adds missing columns to existing tables
    - Safe to run multiple times (idempotent)
    """
    messages = []
    
    try:
        # Get current database state
        existing_tables = get_table_names()
        
        # Define expected schema with columns and types
        expected_schema = {
            'seller_mapping': {
                'id': 'INTEGER',
                'supplier_id': 'INTEGER',
                'gstin': 'VARCHAR',
                'supplier_name': 'VARCHAR',
                'last_updated': 'DATETIME',
            },
            'flipkart_orders': {
                'seller_gstin': 'VARCHAR',
            },
            'flipkart_returns': {
                'seller_gstin': 'VARCHAR',
            },
            'amazon_orders': {
                'seller_gstin': 'VARCHAR',
            },
            'amazon_returns': {
                'seller_gstin': 'VARCHAR',
            },
        }
        
        # Step 1: Create all missing tables
        if not existing_tables:
            messages.append("📋 Creating all database tables...")
            Base.metadata.create_all(engine)
            messages.append("✅ All tables created")
            return messages
        
        # Check if seller_mapping table exists, if not create all tables
        if 'seller_mapping' not in existing_tables:
            messages.append("📋 seller_mapping table missing - creating all tables...")
            Base.metadata.create_all(engine)
            messages.append("✅ All tables created")
            return messages
        
        # Step 2: Add missing columns to existing tables
        with engine.connect() as conn:
            for table_name, columns in expected_schema.items():
                if table_name not in existing_tables:
                    # Table doesn't exist, create it
                    messages.append(f"📋 Creating missing table: {table_name}")
                    # Use Base.metadata to create just this table
                    table = Base.metadata.tables.get(table_name)
                    if table is not None:
                        table.create(engine, checkfirst=True)
                        messages.append(f"✅ Created table: {table_name}")
                    continue
                
                # Check for missing columns
                existing_cols = get_table_columns(table_name)
                
                for col_name, col_type in columns.items():
                    if col_name not in existing_cols:
                        messages.append(f"📋 Adding column {col_name} to {table_name}")
                        try:
                            # Add the column
                            conn.execute(text(f'ALTER TABLE {table_name} ADD COLUMN {col_name} {col_type}'))
                            conn.commit()
                            messages.append(f"✅ Added column: {table_name}.{col_name}")
                        except Exception as e:
                            messages.append(f"⚠️  Column {table_name}.{col_name} may already exist: {str(e)[:50]}")
            
            # Step 3: Create indexes for seller_gstin columns
            try:
                # Check if indexes exist, create if missing
                inspector = inspect(engine)
                
                tables_needing_index = [
                    'flipkart_orders', 'flipkart_returns',
                    'amazon_orders', 'amazon_returns'
                ]
                
                for table_name in tables_needing_index:
                    if table_name not in existing_tables:
                        continue
                    
                    indexes = inspector.get_indexes(table_name)
                    index_names = {idx['name'] for idx in indexes}
                    index_name = f'ix_{table_name}_seller_gstin'
                    
                    if index_name not in index_names:
                        messages.append(f"📋 Creating index on {table_name}.seller_gstin")
                        try:
                            conn.execute(text(f'CREATE INDEX {index_name} ON {table_name} (seller_gstin)'))
                            conn.commit()
                            messages.append(f"✅ Created index: {index_name}")
                        except Exception:
                            messages.append(f"Index {index_name} may already exist")
            
            except Exception as e:
                messages.append(f"⚠️  Index creation: {str(e)[:50]}")
        
        if not messages:
            messages.append("✅ Database schema is up-to-date")
        
        return messages
        
    except Exception as e:
        messages.append(f"❌ Migration error: {str(e)}")
        logger.error(f"Auto-migration failed: {e}", exc_info=True)
        return messages

def verify_multi_seller_setup() -> list:
    """
    Verify that multi-seller infrastructure is properly set up.
    Returns list of status messages.
    """
    messages = []
    
    db = SessionLocal()
    try:
        # Check if seller_mapping table exists and has data
        from models import SellerMapping
        mapping_count = db.query(SellerMapping).count()

        if mapping_count == 0:
            messages.append("No seller mappings found. Import GST data to create mappings.")
        else:
            messages.append(f"{mapping_count} seller mapping(s) configured")
    except Exception as e:
        messages.append(f"Verification error: {str(e)[:50]}")
    finally:
        db.close()
    
    return messages

if __name__ == "__main__":
    print("=== RUNNING DATABASE AUTO-MIGRATION ===\n")
    
    migration_msgs = auto_migrate()
    for msg in migration_msgs:
        print(msg)
    
    print("\n=== VERIFYING MULTI-SELLER SETUP ===\n")
    
    verify_msgs = verify_multi_seller_setup()
    for msg in verify_msgs:
        print(msg)
    
    print("\n=== MIGRATION COMPLETE ===")
