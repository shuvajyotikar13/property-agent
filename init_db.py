import chdb.session as chs
import os

# Define the path where the database will be stored inside the image
DB_PATH = "/app/chdb_data"

def initialize_database():
    print(f"Initializing chDB at {DB_PATH}...")
    
    # Create a persistent session
    sess = chs.Session(DB_PATH)
    
    # 1. Create the UK Property Price Paid table
    sess.query("CREATE DATABASE IF NOT EXISTS uk_data")
    
    print("Downloading and inserting sample data from S3...")
    # We use the S3 table function to stream data directly into our local chDB
    # LIMIT 10000 ensures we don't blow up the container image size
    # Updated query with the correct GCS bucket path
    sess.query("""
        CREATE TABLE IF NOT EXISTS uk_data.property_prices ENGINE = MergeTree ORDER BY post_code AS
        SELECT 
            price,
            toDate(parseDateTimeBestEffort(date)) AS date,
            post_code,
            property_type,
            is_new,
            duration,
            street,
            locality,
            town,
            district,
            county
        FROM gcs(
            'https://storage.googleapis.com/uk_property_prices_test/uk_prices.csv.zst', 
            'CSVWithNames', 
            'uuid String, price UInt32, date String, post_code String, property_type String, is_new String, duration String, street String, locality String, town String, district String, county String, category String, status String'
        )
        LIMIT 20000
    """)
    
    # 2. Create the Agent Memory table with Vector support
    # We store embeddings as Arrays of Float32
    sess.query("CREATE DATABASE IF NOT EXISTS agent_state")
    sess.query("""
        CREATE TABLE IF NOT EXISTS agent_state.conversation_memory (
            role String,
            content String,
            created_at DateTime64(3) DEFAULT now()
            ) ENGINE = MergeTree() 
            ORDER BY created_at;
            """)
    
    # Verify data
    result = sess.query("SELECT count() FROM uk_data.property_prices", "JSON")
    print(f"Database initialized. Row count: {str(result).strip()}")

if __name__ == "__main__":
    initialize_database()
