import chdb.session as chs
import json
from typing import List

class ChDBMemory:
    def __init__(self, db_path="/app/chdb_data"):
        self.session = chs.Session(db_path)

    def save_interaction(self, role: str, content: str):
        """Saves a message with a timestamp."""
        safe_content = content.replace("'", "''")
        
        sql = f"""
        INSERT INTO agent_state.conversation_memory (role, content, created_at)
        VALUES ('{role}', '{safe_content}', now())
        """
        self.session.query(sql)

    def get_recent_context(self, limit: int = 5) -> List[str]:
        """Fetches the N most recent messages in chronological order."""
        sql = f"""
            SELECT content FROM agent_state.conversation_memory 
            ORDER BY created_at DESC LIMIT {limit}
        """
        try:
            res = self.session.query(sql, "JSON")
            data = json.loads(res.bytes()).get('data', [])
            # Reverse to get oldest-to-newest order for the LLM
            return [item['content'] for item in data][::-1]
        except Exception:
            return []
