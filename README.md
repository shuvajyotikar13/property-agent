# 🏠 UK Property Agent: Self-Contained Agentic Analytics

This repository implements a **"Stateful AI Agent"** capable of high-performance analytical queries and semantic memory retrieval without an external database. By embedding **chDB** (an in-process ClickHouse engine) and **Agno** directly into a **Google Cloud Run** container, this agent carries its own dataset and conversation history directly in its "DNA".

---

## 🏗️ Architecture: The "Fat Container" Pattern

Traditional agent architectures look like a hub-and-spoke model where the agent sits in the middle and reaches out over the network to a Vector DB for memory and a SQL DB for structured data. This approach collapses that stack into a single deployable unit.

[Image of a software architecture diagram showing Agno, chDB, and Google Cloud Run integrated into a single container]

* **The Brain (Agno):** Handles the reasoning, conversation state, and tool selection with a tiny memory footprint (~6656 bytes).
* **The Memory Engine (chDB):** An in-process ClickHouse engine that runs inside the Python interpreter, performing OLAP queries on local files without a network socket.
* **The Body (Google Cloud Run):** The serverless wrapper that hosts the brain and engine, providing instant CPU bursts and scaling to zero when idle.

---

## 🚀 Key Features

* **Data "Baking":** Uses `init_db.py` to process raw data into highly optimized, indexed ClickHouse files during the Docker build phase.
* **Zero-Latency Analytics:** Performs vectorized SQL scans on 20,000+ rows in milliseconds because

## ⚙️ Getting Started

### 1. Pre-requisites

     a. Google Cloud Project with Cloud Run enabled.

     b. Google AI Studio API Key (Gemini 3.0 Flash).

     c. Docker installed locally.  
     
### 2. Local Setup & Testing

     # Clone the repository
    git clone [https://github.com/shuvajyotikar/property-agent.git](https://github.com/shuvajyotikar/property-agent.git)
    cd property-agent

    # Build and run with Docker Compose
    docker-compose up --build
### 3. Deploy to Google Cloud Run
  
Deployment is a single command. The Dockerfile ensures the database is "baked" into the container before it goes live.

     gcloud run deploy property-agent \
     --source . \
     --set-env-vars GOOGLE_API_KEY=[YOUR_KEY] \
     --region us-central1 \
     --allow-unauthenticated

## 📝 Verification

The "Deep Data" Test: Ask a question requiring the baked-in dataset.

    curl -X POST "https://[YOUR-SERVICE-URL]/chat" \
    -H "Content-Type: application/json" \
    -d '{"text": "What is the average price of all properties in the database?"}'

## 🔗 Resources

Author: [Shuva Jyoti Kar](https://github.com/shuvajyotikar13), [Shruti Mantri](https://github.com/shrutimantri)

Article: [The End of Stateless AI: Building Self-Contained Data Agents](https://medium.com/@shuva.jyoti.kar.87/the-end-of-stateless-ai-building-self-contained-data-agents-with-google-cloud-run-3d7ced47d34e)

Frameworks: Agno, chDB, Google Cloud Run
