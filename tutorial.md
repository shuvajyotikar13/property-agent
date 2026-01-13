author:      Shruti Mantri, Shuva Jyoti Kar
summary:     Build persistent, self-contained data agents using Agno, chDB, and Google Cloud Run.
id:          data-agents
categories:  cloud, ai, big-data
status:      Published
Feedback Link: https://github.com/data_agents/issues

# Building Self-Contained Data Agents using Google Cloud Run

## Introduction
Duration: 2:00

For too long, AI agents have been built as just “brains” — brilliant at reasoning, but fundamentally disconnected from the massive datasets they need to analyze. Traditionally, this meant high latency, complex VPC peering, and expensive external database connections.

But what if your agent was the database?
This codelab teaches you how to collapse this stack into a single, high-performance deployable unit using **Agno**, **chDB**, and **Google Cloud Run**.By embedding the vectorised power of **chDB** and the orchestration of **Agno** directly into a **Google Cloud Run** container, we can finally move the compute to the data. This architecture allows us to build **stateful, self-contained units** that carry their own analytical engines and datasets - scaling to zero when idle, yet delivering sub-second insights on millions of rows the moment they wake up. 

It's time to stop shipping data to the brain and start baking the data into the agent

### Architecture: When Container is the Database

While traditional agent architectures look like a hub-and-spoke model with the agent (compute) sitting in the middle and reaching out over the network to a Vector DB for memory and a SQL DB for structured data, our approach collapses this stack into a single deployable unit.

* **The Brain (Agno):** Using Agno for rapid reasoning and tool selection.
* **The Memory Engine (chDB):** Leveraging an in-process ClickHouse engine for local OLAP queries. Also utilising ClickHouse's native *L2Distance* function for similarity search.
* **The Body (Google Cloud Run):** Wrapping it all in a serverless environment that providing instant CPU burst, and scales to zero when not in use.

---
## Initializing git

```bash
# 1. Create the project folder
mkdir property-agent
cd property-agent

# 2. Initialize Git
git init
```

## Setting up the repository structure

We will keep a flat structure (all files in the root). This is the easiest since the Dockerfile command COPY . . works without needing path adjustments. We will create all the files in the following series of steps

```bash
property-agent/
├── .env                  # Your API Keys (Ignored by Git)
├── .env.example          # Template for other developers
├── .gitignore            # Files to exclude from Git
├── Dockerfile            # Builds the image + runs init_db.py
├── README.md             # Documentation
├── agent.py              # Agno Agent logic
├── chdb_tool.py          # SQL Tool for the Agent
├── docker-compose.yml    # Local testing configuration
├── init_db.py            # Script to bake the DB into the image
├── main.py               # FastAPI entry point
├── memory.py             # Vector search logic
└── requirements.txt      # Python dependencies
```

## Creating the .env file

```bash
GOOGLE_API_KEY=your_gemini_api_key_here
```

## Creating the .gitignore file

It is very crucial to ensure you don't accidentally commit your chdb_data (which might be large) or your .env keys.

```bash
# Python
__pycache__/
*.pyc
*.pyo
*.pyd
.Python
env/
venv/
.venv/

# Environment Variables
.env

# Local Database (if you run init_db.py locally)
chdb_data/
chdb_data_*/

# IDE settings
.vscode/
.idea/
```
## Creating the requirements.txt file

Create the requirements.txt file with the following inputs

```bash
phidata
google-genai
fastapi
uvicorn
chdb>=2.0
```

## Creating the docker-compose.yml file

This file allows you to spin up the agent locally with one command. We map port 8080 so you can access the FastAPI endpoint just like you would on the cloud.

```yml
version: '3.8'

services:
  property-agent:
    platform: linux/arm64
    build:
      context: .
      dockerfile: Dockerfile
    container_name: local-property-agent
    ports:
      - "8080:8080"
    env_file:
      - .env
    environment:
      - PORT=8080
      - HOST=0.0.0.0
    # Note: We do NOT use volumes here (e.g., - .:/app)
    # Why? Because init_db.py creates the database inside the container image
    # at build time. If we mount a volume, we might overwrite that
    # internal data with our empty local folder.
```


## Setting up the Memory Engine (chDB)

The magic of this architecture is **chDB**. It allows us to query parquet or CSV files using SQL directly in the container's memory without a standalone database server.

### Setting up the Data Engine

Create a file named `chdb_tool.py`:

```python
import chdb.session as chs
import json

class ChDBToolkit:
    def __init__(self, db_path="/app/chdb_data"):
        self.db_path = db_path

    def run_sql_query(self, query: str) -> str:
        """Executes SQL queries against the local property database."""
        try:
            sess = chs.Session(self.db_path)
            res = sess.query(query, "JSON")
            return res.bytes().decode('utf-8')
        except Exception as e:
            return f"Error executing query: {str(e)}"
```

### Setting up the Memory

A standard AI has a "short-term" memory (the current chat window). This ChDBMemory class gives it a "long-term" memory. If you talked about your favorite color three weeks ago, this system allows the agent to pull that specific fact back into its current context when relevant.

This is a custom chDB implementation for vector search using Google Gemini for embeddings.

Create a file named `memory.py`:

```python
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
```

###Initializing the Memory###

The init_db.py script is the "Construction Crew" of your container. Its purpose is to transform a generic Python environment into a specialized Data Engine before the application ever goes live.

In a serverless environment like Google Cloud Run, you can't rely on a database being "already there." init_db.py ensures the data is physically bundled into the container's DNA.

1. Data "Baking" (The Core Purpose)

On Google Cloud Run, the file system is read-only after the container starts (mostly). If you try to download 20,000 rows of property data every time a user asks a question, the agent will be painfully slow and expensive.

init_db.py runs during the Docker Build phase. It:

a. Downloads the raw CSV/Parquet data from S3.

b. Uses chDB to convert that raw data into highly optimized, indexed ClickHouse files.

c. Saves those files into a folder (e.g., /app/chdb_data) that becomes a permanent part of the container image.

2. Schema Enforcement
The script defines the "rules" of your data. It creates the tables and column types (Strings, UInt32, Arrays) so that when the Agent starts up, it doesn't have to guess if a column is named price or amount.

It also sets up the Vector Search capability by initializing the agent_state.conversation_memory table with the correct dimensions for your embeddings.

3. Performance Optimization
By running init_db.py beforehand, you perform the "heavy lifting" once.

**Without it**: Every new user request triggers a data download (Slow/Expensive).

**With it**: The data is "Warm." chDB can query the local files in milliseconds as soon as the container spins up.

Lets create the init_db.py

```python
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
    # Updated query with the correct Amazon S3 bucket path
    sess.query("""
        CREATE TABLE IF NOT EXISTS uk_data.property_prices ENGINE = MergeTree ORDER BY post_code AS
        SELECT
            price,
            toDate(parseDateTimeBestEffort(date)) AS date, -- Convert the DateTime string to a Date object
            post_code,
            property_type,
            is_new,
            duration,
            street,
            locality,
            town,
            district,
            county
        FROM s3(
            'https://learn-clickhouse.s3.us-east-2.amazonaws.com/uk_property_prices/uk_prices.csv.zst',
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
            id UUID DEFAULT generateUUIDv4(),
            role String,
            content String,
            embedding Array(Float32),
                        timestamp DateTime DEFAULT now()
        ) ENGINE = MergeTree ORDER BY timestamp
    """)

    # Verify data
    result = sess.query("SELECT count() FROM uk_data.property_prices", "JSON")
    print(f"Database initialized. Row count: {str(result).strip()}")

if __name__ == "__main__":
    initialize_database()
```

## Coding the Agent "Brain" with Agno

When choosing an orchestration framework, developers often default to LangChain. However, in a serverless environment like Google Cloud Run, cold starts and memory footprints are your biggest enemies.

Recent benchmarks show that Agno (formerly Phidata) instantiates agents on a min 500x faster than graph-based alternatives, with a memory footprint of just ~3.8 KiB. In the world of Cloud Run, this means:
1. **Sub-second Cold Starts**: Your container is ready to "think" almost instantly.
2. **Higher Concurrency**: You can pack hundreds of agent sessions into a single 512MB RAM instance, drastically reducing your Google Cloud bill.

By using its native FastAPI integration, we can package our agent as a lightweight container that boots in milliseconds.

Create a python file named "agent.py"

```python
import os
from phi.agent import Agent
from phi.model.google import Gemini
from chdb_tool import ChDBToolkit
from memory import ChDBMemory

# Initialize specialized tools and memory
db_tool = ChDBToolkit()
memory = ChDBMemory()

agent = Agent(
    model=Gemini(id="gemini-3.0-flash"),
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
```

We would also need to create another file named "main.py"

```python
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from agent import chat_with_agent
from pydantic import BaseModel

app = FastAPI()

class Query(BaseModel):
    text: str

@app.post("/chat")
async def chat_endpoint(query: Query):
    return StreamingResponse(chat_with_agent(query.text), media_type="text/plain")
```

In this architecture, *main.py* serves as the Operational Interface or the "Entry Point" for the entire system. Without it, you have a "brain" (the agent) but no "body" to connect it to the outside world.

1. It Creates the Web Server
AI agents are just Python logic; they don't inherently know how to listen for internet traffic. main.py uses FastAPI to create a web server that listens on a specific port (usually 8080). When Google Cloud Run receives a request from a user, it passes that request to main.py.

2. It Manages the "Stateless" Lifecycle
Google Cloud Run is ephemeral. main.py handles the orchestration needed to make it feel persistent:

a. The Handshake: It receives the JSON request and extracts the session_id.

b. The Retrieval: It tells memory.py to go into the database and find who this user is.

c. The Execution: It feeds that history into agent.py to get an intelligent answer.

d. The Persistence: Once the agent is done talking, main.py ensures the new conversation is saved back into the database before the container shuts down.

3. It Handles "Streaming"
Standard scripts usually wait for a full answer before showing anything. main.py uses FastAPI's StreamingResponse to send the agent's answer word-by-word. This is the difference between a user waiting 10 seconds for a block of text and seeing an interactive, "typing" effect immediately.

4. It Provides API Documentation
Because main.py uses FastAPI, it automatically generates a /docs (Swagger) endpoint. This allows other developers (or your own frontend) to see exactly what data the agent expects without having to read through all your internal logic.

## Creating the Docker Image

This is where the architecture comes together. Our Dockerfile combines the Python runtime, the Agno framework, the chDB memory engine, into one portable artifact.

```bash
# Use a Python 3.10 slim image
FROM python:3.10-slim

# Install system dependencies required for chDB and networking
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies directly
# We include google-generativeai and phidata (agno)
RUN pip install --no-cache-dir \
    phidata \
    google-generativeai \
    chdb \
    fastapi \
    uvicorn \
    pydantic

# Copy the application code
COPY . .

# Create the data directory and ensure permissions
RUN mkdir -p /app/chdb_data && chmod -R 777 /app/chdb_data

# Run the database initialization during build
# This "bakes" the S3 data into the image
RUN python init_db.py

# Expose the FastAPI port
EXPOSE 8080

# Run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
```

## Build and Run with Docker Compose

This is the moment of truth. This command will build the image, run init_db.py (downloading the UK property data), and start the server.

```bash
...
 ✔ Image property-agent-property-agent Built                                                                                                                                            2.1s 
 ✔ Container local-property-agent        Recreated                                                                                                                                        0.0s 
Attaching to local-property-agent
local-property-agent  | /usr/local/lib/python3.10/site-packages/google/api_core/_python_version_support.py:266: FutureWarning: You are using a Python version (3.10.19) which Google will stop supporting in new releases of google.api_core once it reaches its end of life (2026-10-04). Please upgrade to the latest Python version, or at least Python 3.11, to continue receiving updates for google.api_core past that date.
local-property-agent  |   warnings.warn(message, FutureWarning)
local-property-agent  | /usr/local/lib/python3.10/site-packages/phi/model/google/gemini.py:19: FutureWarning: 
local-property-agent  | 
local-property-agent  | All support for the `google.generativeai` package has ended. It will no longer be receiving 
local-property-agent  | updates or bug fixes. Please switch to the `google.genai` package as soon as possible.
local-property-agent  | See README for more details:
local-property-agent  | 
local-property-agent  | https://github.com/google-gemini/deprecated-generative-ai-python/blob/main/README.md
local-property-agent  | 
local-property-agent  |   import google.generativeai as genai
local-property-agent  | INFO:     Started server process [1]
local-property-agent  | INFO:     Waiting for application startup.
local-property-agent  | INFO:     Application startup complete.
local-property-agent  | INFO:     Uvicorn running on http://0.0.0.0:8080 (Press CTRL+C to quit)
```
Once you see Uvicorn running on http://0.0.0.0:8080, your agent is live with the embedded database.

```bash
curl -X POST "http://localhost:8080/chat" \
     -H "Content-Type: application/json" \
     -d '{"text": "What is the average price of a house in London?"}'

 - Running: run_sql_query(query=SELECT AVG(price) FROM uk_data.property_prices WHERE city = 'London')

My apologies, I made a mistake in the query. The correct column name for city is 'town'. Let me try again.

 - Running: run_sql_query(query=SELECT AVG(price) FROM uk_data.property_prices WHERE town = 'London')

Okay, the average price is null. This probably means there's no exact match for 'London' in the town column. 
Perhaps there are London boroughs listed instead. I will search for all records containing London in the town column.

 - Running: run_sql_query(query=SELECT AVG(price) FROM uk_data.property_prices WHERE town LIKE '%London%')

It seems there is no data for London in the `town` column. I will try searching for London in the `county` column.

 - Running: run_sql_query(query=SELECT AVG(price) FROM uk_data.property_prices WHERE county = 'London')

I am having trouble locating London in the database. I will try a broader search to see what entries are available.

 - Running: run_sql_query(query=SELECT DISTINCT town FROM uk_data.property_prices LIMIT 10)

 - Running: run_sql_query(query=SELECT AVG(price) FROM uk_data.property_prices WHERE town = 'LONDON')

The average price of a house in LONDON is 133217.60.
```


## Finally, Deploying on Google Cloud Run

###The Reasoning###

Deploying this image to Cloud Run is the final piece of the puzzle.
1. Scale-to-Zero: Analytical agents are often used sporadically. Cloud Run spins the container down completely when not in use, costing you nothing.
2. CPU Bursting: When a request comes in, Cloud Run spins up the container instantly. Crucially, you can allocate significant CPU (e.g., 4 or 8 vCPUs) which chDB will utilize heavily for the few hundred milliseconds it takes to crunch millions of rows.

Since this structure mirrors the layout Google Cloud Run expects, deployment is just one command:

``` bash
# Set your Project ID
PROJECT_ID=$(gcloud config get-value project)

# Deploy to Cloud Run
gcloud run deploy property-agent \
  --image gcr.io/$PROJECT_ID/property-agent \
  --set-env-vars GOOGLE_API_KEY=[YOUR_KEY_HERE] \
  --region us-central1 \
  --allow-unauthenticated

```

To verify your deployment on Google Cloud Run, you need to confirm two things: that the FastAPI server is reachable and that the Embedded chDB is correctly querying the "baked-in" data.
Here is the two-step verification process.

1. **The "Health Check" (Basic Connectivity)**
Once the deployment finishes, Google Cloud will provide a Service URL (e.g., https://property-agent-xyz.a.run.app). Open your browser or use curl to check if the container is alive.

```bash
# Replace with your actual Cloud Run URL
export SERVICE_URL="https://property-agent-xyz.a.run.app"

curl -I $SERVICE_URL/docs
```
**What to look for**: A 200 OK response. This confirms the FastAPI server is running and the container started successfully despite the heavy data-loading process.

2. **The "Deep Data" Test (SQL Verification)**
The real test is asking a question that requires the embedded ClickHouse data. If the agent answers correctly, it proves chDB initialized the S3 data during the build.

**Run this command in your terminal:**

```bash
curl -X POST "https://property-agent-611028802760.us-central1.run.app/chat" \
     -H "Content-Type: application/json" \
     -d '{"text": "Run a SQL query to find the average price of all properties in the database."}'

 - Running: run_sql_query(query=SELECT AVG(price) FROM uk_data.property_prices)

The average price of all properties in the database is 69027.3917.
```
**Success Criteria**: The agent should return a specific number (e.g., "The average price is £69027.3917").
**Failure Sign**: If the agent says "I don't have access to data" or "The table doesn't exist," the init_db.py script likely failed during the Docker build.

## Inspecting Logs (The "Under the Hood" View)

If things aren't working, Google Cloud Logs are your best friend. In the Google Cloud Console, go to Cloud Run > Your Service > Logs.
1. Look for these specific log entries that we programmed into init_db.py:

```bash
Initializing chDB at /app/chdb_data...
Downloading and inserting sample data from S3...
Database initialized. Row count: 20000
```

Pro Tip: If you see "Memory Limit Exceeded" in the logs, increase your Cloud Run Memory to 2GB or 4GB. ClickHouse is highly efficient, but "baking" and querying 20,000 rows plus running an LLM agent requires a bit of breathing room

**Finally**
Remember to scale it down to prevent unnecessary billing
```bash
gcloud run services update property-agent --scaling=0 --region=us-central1

✓ Updating... Done.                                                                                                                                                                         
Done.                                                                                                                                                                                  Service [property-agent] has been updated
```

## Conclusion: From Chatbots to Data-Aware Agents

By completing this project, we have moved beyond the "Chatbot" era and entered the **"Agentic Analytics"** era. We didn't just build a program that talks; we built a self-contained intelligence that carries its own library (Data) and its own diary (Memory).

We’ve learned that high-performance AI doesn't always require massive, expensive database clusters. By "baking" **chDB** directly into a **Google Cloud Run** container, we created a portable, serverless analyst that can reason over tens of thousands of records in milliseconds—all while remaining cost-effective by scaling to zero when not in use.

---

### **3 Key Takeaways**

1. **Zero-Latency Data Baking** : By using the Docker build layer to host your chDB files, you turn Google Cloud Run’s high-speed internal SSD storage into a localized data warehouse, bypassing the "Data-Blindness" of typical AI.

2. **Autonomous Scaling & Savings** : You gain a production-grade analytics platform that scales to zero. You only pay for the exact milliseconds the Gemini model is "thinking" and the ClickHouse engine is "querying."

3. **The "Unified Container" Pattern** : Google Cloud Run proves that the best way to ship AI in 2026 is the "Fat Container"—bundling the Brain (Agent), the Memory (Vector DB), and the Knowledge (SQL DB) into one single, portable unit that runs anywhere.

##
