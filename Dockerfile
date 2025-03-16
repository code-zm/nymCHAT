FROM python:3.11-slim

# Set the working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y curl

# Copy requirements.txt and install dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire application source code into the container
COPY . /app

# Make sure install.sh is executable
RUN chmod +x scripts/install.sh

RUN chmod +x scripts/entrypoint.sh

# Run install.sh inside Docker (automated setup, NO user input)
RUN scripts/install.sh

# Set entrypoint to run the Nym client
ENTRYPOINT ["scripts/entrypoint.sh"]

# Start the main Python application