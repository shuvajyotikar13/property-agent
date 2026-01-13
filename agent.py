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
    context = memory.retrieve_context(user_query)
    context_str = "\n".join(context)
    
    # 2. Add context to the prompt (simplified RAG)
    full_prompt = f"Context from previous messages:\n{context_str}\n\nUser Question: {user_query}"
    
    # 3. Get response
    response_stream = agent.run(full_prompt, stream=True)
    
    full_response = ""
    for chunk in response_stream:
        full_response += chunk.content
        yield chunk.content
        
    # 4. Save the interaction
    memory.save_interaction("user", user_query)
    memory.save_interaction("agent", full_response)
