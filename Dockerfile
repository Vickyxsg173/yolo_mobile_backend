FROM python:3.10-slim

WORKDIR /app

# Install dependencies first for Docker layer caching
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the backend code
COPY backend/ .

# Run the FastAPI server using the port Railway provides
CMD uvicorn main:app --host 0.0.0.0 --port $PORT
