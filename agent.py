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
    # 1. Retrieve hybrid context
    context = memory.retrieve_full_context(user_query)
    
    similar_results = context.get('similar', [])
    recent_data = context.get('recent', [])

    # 2. Filter Similar Context by Threshold
    # (Lower score = higher similarity for L2Distance)
    RELEVANCE_THRESHOLD = 0.8 
    valid_similar = [
        item['content'] for item in similar_results 
        if item['score'] < RELEVANCE_THRESHOLD
    ]

    # 3. Build the Hybrid Prompt
    prompt_sections = ["You are a professional Property Agent assistant."]

    # Always add Recent History if it exists
    if recent_data:
        history_str = "\n".join(recent_data)
        prompt_sections.append(f"--- RECENT CONVERSATION HISTORY ---\n{history_str}")

    # Only add Similar Context if it passes the threshold
    if valid_similar:
        similar_str = "\n".join(valid_similar)
        prompt_sections.append(f"--- RELEVANT PAST FACTS ---\n{similar_str}")
        print(f"--- Hybrid: Injected {len(valid_similar)} similar facts ---")
    else:
        print("--- Hybrid: No similar facts met the threshold ---")

    # Final User Question
    prompt_sections.append(f"CURRENT USER QUESTION: {user_query}")
    
    full_prompt = "\n\n".join(prompt_sections)

    # 4. Execute Streaming Response
    response_stream = agent.run(full_prompt, stream=True)
    full_response = ""
    for chunk in response_stream:
        content = getattr(chunk, 'content', str(chunk))
        full_response += content
        yield content

    # 5. Save the interaction
    memory.save_interaction("user", user_query)
    memory.save_interaction("agent", full_response)
