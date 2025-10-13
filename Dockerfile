# Use official Python runtime as base image
FROM python:3.12-slim

# Set working directory in container
WORKDIR /app

# Install system dependencies if needed
RUN apt-get update && apt-get install -y \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first (for better caching)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire application
COPY . .

# Expose the port your app runs on
EXPOSE 3000

# Set environment variables
ENV PORT=3000
ENV PYTHONUNBUFFERED=1

# Command to run the application
CMD ["uvicorn", "src.index:app", "--host", "0.0.0.0", "--port", "3000"]