import os
import chdb.session as chs
import json
from phi.model.google import Gemini
from phi.embedder.google import GeminiEmbedder
from typing import List, Dict

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

        # Added 'created_at' timestamp for chronological retrieval
        sql = f"""
        INSERT INTO agent_state.conversation_memory (role, content, embedding, created_at)
        VALUES ('{role}', '{safe_content}', {emb_str}, now())
        """
        self.session.query(sql)

    def get_similar_conversations(self, query: str, limit: int = 3) -> List[dict]:
        """Returns list of dicts with content and their similarity score."""
        query_emb = self.embedder.get_embedding(query)
    
        # Calculate distance and alias it as 'score'
        sql = f"""
        SELECT content, L2Distance(embedding, {str(query_emb)}) as score
        FROM agent_state.conversation_memory
        ORDER BY score ASC
        LIMIT {limit}
        """    
        try:
            res = self.session.query(sql, "JSON")
            rows = json.loads(res.bytes())
            # Return both content and score for filtering
            return [{"content": r['content'], "score": r['score']} for r in rows.get('data', [])]
        except Exception as e:
            print(f"Error: {e}")
            return []

    def get_last_n_conversations(self, n: int = 5) -> List[str]:
        """Retrieves the most recent N interactions (chronological)."""
        sql = f"""
        SELECT content FROM agent_state.conversation_memory
        ORDER BY created_at DESC
        LIMIT {n}
        """
        # We reverse it at the end so it's in natural order (oldest to newest)
        results = self._execute_and_parse(sql)
        return results[::-1] 

    def retrieve_full_context(self, query: str, similar_limit: int = 3, recent_limit: int = 3) -> Dict[str, List[str]]:
        """Helper to get both at once for the LLM prompt."""
        return {
            "similar": self.get_similar_conversations(query, similar_limit),
            "recent": self.get_last_n_conversations(recent_limit)
        }

    def _execute_and_parse(self, sql: str) -> List[str]:
        """Internal helper to handle chdb JSON parsing."""
        try:
            res = self.session.query(sql, "JSON")
            rows = json.loads(res.bytes())
            return [r['content'] for r in rows.get('data', [])]
        except Exception as e:
            print(f"Error retrieving from chdb: {e}")
            return []
