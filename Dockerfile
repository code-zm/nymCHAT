FROM python:3.11-slim

# Set the working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y curl gettext

# Copy the requirements file and install dependencies
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# Copy the required directories in one command
COPY server/*.py server/

COPY scripts/* scripts/

COPY .env.example .env.example

COPY password.txt password.txt

# Ensure the shell scripts are executable
RUN chmod +x scripts/*.sh

# Run the installation script
RUN scripts/install.sh

EXPOSE 1977
# Set entrypoint to run the Nym client
ENTRYPOINT ["scripts/entrypoint.sh"]
