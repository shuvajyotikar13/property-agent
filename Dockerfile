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