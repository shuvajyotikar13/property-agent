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
    # 1. Get only the last 5 messages
    recent_msgs = memory.get_recent_context(limit=5)

    # 2. Build a simple prompt with history
    if recent_msgs:
        history_str = "\n".join(recent_msgs)
        full_prompt = f"Recent conversation history:\n{history_str}\n\nUser Question: {user_query}"
    else:
        full_prompt = user_query

    # 3. Stream Response
    response_stream = agent.run(full_prompt, stream=True)
    full_response = ""
    for chunk in response_stream:
        content = getattr(chunk, 'content', str(chunk))
        full_response += content
        yield content

    # 4. Save to ChDB
    memory.save_interaction("user", user_query)
    memory.save_interaction("agent", full_response)
