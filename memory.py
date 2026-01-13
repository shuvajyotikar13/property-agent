import os
import chdb.session as chs
import json
from phi.model.google import Gemini
from phi.embedder.google import GeminiEmbedder
from typing import List

class ChDBMemory:
    def __init__(self, db_path="/app/chdb_data"):
        self.db_path = db_path
        self.session = chs.Session(self.db_path)
        # Using Gemini for embeddings to match your ecosystem
        self.embedder = GeminiEmbedder(
    model="models/gemini-embedding-001", 
    api_key=os.getenv("GOOGLE_API_KEY")
)

    def save_interaction(self, role: str, content: str):
        # Generate embedding for the content
        # Note: In production, ensure this returns a list of floats
        embedding = self.embedder.get_embedding(content)
        
        # Format embedding as a string representation of an array for SQL: [0.1, 0.2, ...]
        emb_str = str(embedding)
        
        # Escape single quotes in content
        safe_content = content.replace("'", "''")
        
        sql = f"""
        INSERT INTO agent_state.conversation_memory (role, content, embedding)
        VALUES ('{role}', '{safe_content}', {emb_str})
        """
        self.session.query(sql)

    def retrieve_context(self, query: str, limit: int = 5) -> List[str]:
        query_emb = self.embedder.get_embedding(query)
        query_emb_str = str(query_emb)
        
        # Use L2Distance for vector similarity (Brute force is fast enough for <100k rows)
        sql = f"""
        SELECT content 
        FROM agent_state.conversation_memory
        ORDER BY L2Distance(embedding, {query_emb_str}) ASC
        LIMIT {limit}
        """
        
        try:
            res = self.session.query(sql, "JSON")
            rows = json.loads(res.bytes())
            return [r['content'] for r in rows.get('data', [])]
        except Exception as e:
            print(f"Error retrieving context: {e}")
            return []
