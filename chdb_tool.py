import chdb.session as chs
import json

class ChDBToolkit:
    def __init__(self, db_path="/app/chdb_data"):
        self.db_path = db_path

    def run_sql_query(self, query: str) -> str:
        """
        Executes a SQL query against the internal UK Property database.
        Use this to find average prices, trends, or specific property details.
        
        Args:
            query (str): The SQL query to execute (e.g., "SELECT avg(price) FROM uk_data.property_prices")
            
        Returns:
            str: The query results in JSON format.
        """
        try:
            # Create a session connected to the persisted path
            sess = chs.Session(self.db_path)
            res = sess.query(query, "JSON")
            return res.bytes().decode('utf-8')
        except Exception as e:
            return f"Error executing query: {str(e)}"
