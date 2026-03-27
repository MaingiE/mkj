import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mkj_cms.settings')
django.setup()

from django.db import connection

cursor = connection.cursor()

# Get all tables in public schema
cursor.execute("""
    SELECT table_name 
    FROM information_schema.tables 
    WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
""")
tables = [row[0] for row in cursor.fetchall()]

if tables:
    # Drop all tables with CASCADE
    cursor.execute("DROP SCHEMA public CASCADE")
    cursor.execute("CREATE SCHEMA public")
    cursor.execute("GRANT ALL ON SCHEMA public TO postgres")
    cursor.execute("GRANT ALL ON SCHEMA public TO public")
    print(f"Dropped {len(tables)} tables: {', '.join(tables)}")
else:
    print("No tables to drop")

print("Production database wiped clean.")
