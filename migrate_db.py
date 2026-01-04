"""
Database migration script to create missing tables.
Run this script to ensure all tables from models.py exist in the database.

⚠️  WARNING: Always backup your database before running migrations!

Usage:
    python migrate_db.py
"""

import sys
from sqlalchemy import inspect, text
from sqlalchemy.exc import OperationalError, DatabaseError

from database import engine
from models import Base

def check_database_connection() -> bool:
    """Test database connectivity before migration.
    
    Returns:
        True if connection successful, False otherwise
    """
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except (OperationalError, DatabaseError) as e:
        print(f"❌ Database connection failed: {e}")
        return False

def get_existing_tables() -> set:
    """Get list of existing tables in the database.
    
    Returns:
        Set of table names currently in database
    """
    inspector = inspect(engine)
    return set(inspector.get_table_names())

def migrate() -> bool:
    """Create all missing tables defined in models.
    
    Returns:
        True if migration successful, False otherwise
    """
    print("=" * 60)
    print("🔄 DATABASE MIGRATION STARTING")
    print("=" * 60)
    
    # Check database connection
    print("\n📡 Checking database connection...")
    if not check_database_connection():
        print("❌ Migration aborted - cannot connect to database")
        print("💡 Check your DATABASE_URL in .env file")
        return False
    print("✅ Database connection verified")
    
    # Get existing tables before migration
    print("\n📋 Scanning existing tables...")
    existing_tables_before = get_existing_tables()
    print(f"   Found {len(existing_tables_before)} existing tables: {', '.join(sorted(existing_tables_before))}")
    
    # Get all tables that should exist
    model_tables = set(Base.metadata.tables.keys())
    new_tables = model_tables - existing_tables_before
    
    if not new_tables:
        print("\n✅ All tables already exist - no migration needed")
        print("=" * 60)
        return True
    
    print(f"\n🆕 Tables to create: {', '.join(sorted(new_tables))}")
    print("\n⚠️  IMPORTANT: This will modify your database!")
    print("   Press CTRL+C within 3 seconds to cancel...")
    
    try:
        import time
        time.sleep(3)
    except KeyboardInterrupt:
        print("\n🛑 Migration cancelled by user")
        return False
    
    # Run migration
    print("\n🔨 Creating new tables...")
    try:
        Base.metadata.create_all(bind=engine)
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        return False
    
    # Verify tables were created
    existing_tables_after = get_existing_tables()
    created_tables = existing_tables_after - existing_tables_before
    
    print("\n" + "=" * 60)
    print("✅ DATABASE MIGRATION COMPLETED SUCCESSFULLY")
    print("=" * 60)
    
    if created_tables:
        print(f"\n📊 Created {len(created_tables)} new table(s):")
        for table in sorted(created_tables):
            print(f"   ✓ {table}")
    
    print(f"\n📈 Total tables in database: {len(existing_tables_after)}")
    print("\n💡 Next steps:")
    print("   1. Test your application: uvicorn main:app --reload")
    print("   2. Verify new tables in database")
    print("   3. Backup your database regularly")
    
    return True

if __name__ == "__main__":
    success = migrate()
    sys.exit(0 if success else 1)
