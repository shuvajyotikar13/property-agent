import os
from phi.agent import Agent
from phi.model.google import Gemini
from chdb_tool import ChDBToolkit
from memory import ChDBMemory

# Initialize specialized tools and memory
db_tool = ChDBToolkit()
memory = ChDBMemory()

agent = Agent(
    model=Gemini(id="gemini-2.0-flash"),
    # Add the ChDB tool function
    tools=[db_tool.run_sql_query],
    # Custom instructions to use the tool
    instructions=[
        "You are a UK Real Estate data analyst.",
        "You have access to a local database via 'run_sql_query'.",
        "The table is 'uk_data.property_prices'.",
        "Always query the database to answer questions about prices, towns, or trends.",
        "Use simple SQL queries."
    ],
    show_tool_calls=True,
    markdown=True
)

def chat_with_agent(user_query: str):
    # 1. Retrieve context
    # We now expect 'similar' to be a list of dicts: [{'content': '...', 'score': 0.4}]
    context = memory.retrieve_full_context(user_query)
    
    similar_results = context.get('similar', [])
    recent_data = context.get('recent', [])

    # 2. Apply Relevance Threshold Check
    # Only keep similar items if the distance score is low (lower = more similar)
    RELEVANCE_THRESHOLD = 0.8 
    
    valid_similar_content = [
        item['content'] for item in similar_results 
        if item['score'] < RELEVANCE_THRESHOLD
    ]

    # 3. Logic Gate
    if valid_similar_content:
        context_str = "\n".join(valid_similar_content)
        full_prompt = f"Found relevant background info:\n{context_str}\n\nQuestion: {user_query}"
        print(f"--- Logic: Similar (Best Score: {similar_results[0]['score']:.4f}) ---")
        
    elif recent_data:
        context_str = "\n".join(recent_data)
        full_prompt = f"Recent history context:\n{context_str}\n\nQuestion: {user_query}"
        print("--- Logic: Recent History (Similarity was too low) ---")
        
    else:
        full_prompt = user_query
        print("--- Logic: Raw Query ---")

    # 4. Run Agent (Streaming)
    response_stream = agent.run(full_prompt, stream=True)
    full_response = ""
    for chunk in response_stream:
        content = getattr(chunk, 'content', str(chunk))
        full_response += content
        yield content

    memory.save_interaction("user", user_query)
    memory.save_interaction("agent", full_response)
