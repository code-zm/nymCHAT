# Use an official Python image as a base
FROM python:3.11-slim

# Install system dependencies required for building native extensions and Rust
RUN apt-get update && apt-get install -y \
    build-essential \
    libssl-dev \
    pkg-config \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory in the container
WORKDIR /app

# Copy requirements.txt and build.sh into the container
COPY requirements.txt build.sh ./

# Copy only the required project directories and files
COPY client/ client/
COPY storage/ storage/
COPY async_ffi/Cargo.toml async_ffi/
COPY async_ffi/Cargo.lock async_ffi/
COPY async_ffi/src/ async_ffi/src/

# Ensure the build script is executable
RUN chmod +x build.sh

# Run the build script to install dependencies, Rust (if needed), and build the Rust extension
RUN ./build.sh

# Expose the port if your application listens on a specific port (adjust if necessary)
EXPOSE 8080

# Launch the client application directly
CMD ["python", "client/runClient.py"]
