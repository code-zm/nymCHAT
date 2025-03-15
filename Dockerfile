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

# Ensure `password.txt` is available inside the container
COPY password.txt /app/password.txt

# Make sure install.sh is executable
RUN chmod +x scripts/install.sh

# Run install.sh inside Docker (automated setup, NO user input)
RUN /app/scripts/install.sh

COPY scripts/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Expose WebSocket port used by the Nym client
EXPOSE 1977

# Set entrypoint to run the Nym client
ENTRYPOINT ["/app/entrypoint.sh"]

# Start the main Python application