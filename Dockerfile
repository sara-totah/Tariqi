# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Install system dependencies required by some Python packages
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    libboost-program-options-dev \
    libboost-system-dev \
    libboost-thread-dev \
    zlib1g-dev \
    libeigen3-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy the dependencies file to the working directory
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Install CAMeL Tools data
RUN camel_data -i ner-arabert

# Copy the application code into the container
COPY ./app /app/app
COPY ./scripts/entrypoint.sh /app/entrypoint.sh

# Make port 8000 available to the world outside this container
EXPOSE 8000

# Define environment variables
ENV PYTHONPATH=/app
ENV ENVIRONMENT=production

# Make the entrypoint script executable
RUN chmod +x /app/entrypoint.sh

# Use the entrypoint script to start services
ENTRYPOINT ["/app/entrypoint.sh"]
