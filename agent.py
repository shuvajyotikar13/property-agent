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
    # 1. Retrieve relevant past context
    context = memory.retrieve_full_context(
        query=user_query, 
        similar_limit=3, 
        recent_limit=5
    )
    
    similar_data = context.get('similar', [])
    recent_data = context.get('recent', [])

    # 2. Logic Check & Prompt Construction
    if similar_data:
        # Case 1: Found semantically similar messages
        context_str = "\n".join(similar_data)
        full_prompt = f"Relevant past context:\n{context_str}\n\nUser Question: {user_query}"
    elif recent_data:
        # Case 2: No similarity found, but we have recent history
        context_str = "\n".join(recent_data)
        full_prompt = f"Recent conversation history:\n{context_str}\n\nUser Question: {user_query}"
    else:
        # Case 3: Fresh conversation (no data yet)
        full_prompt = user_query

    # 3. Get response
    response_stream = agent.run(full_prompt, stream=True)

    full_response = ""
    for chunk in response_stream:
        # Note: Ensure 'chunk' has a '.content' attribute based on your specific Agent SDK
        content = getattr(chunk, 'content', str(chunk))
        full_response += content
        yield content

    # 4. Save the interaction to ChDB
    memory.save_interaction("user", user_query)
    memory.save_interaction("agent", full_response)
