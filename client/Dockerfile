# Stage 1: Build Stage
FROM python:3.11-slim AS builder

# Install build dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libssl-dev \
    pkg-config \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy the build script and Rust project files
COPY build.sh .
COPY async_ffi/ async_ffi/
COPY requirements.txt .

# Make sure build.sh is executable
RUN chmod +x build.sh

# Run the build script to install Rust (if needed) and build the wheel
RUN ./build.sh

# Copy the built wheel to a dedicated folder for later retrieval
RUN mkdir /wheel && cp async_ffi/target/wheels/*.whl /wheel/

# Stage 2: Final (runtime) Stage
FROM python:3.11-slim

WORKDIR /app

# Copy only the files needed at runtime
COPY requirements.txt ./
COPY client/ client/
COPY storage/ storage/

# Copy the pre-built wheel from the builder stage
COPY --from=builder /wheel/ /wheel/

# Install runtime Python dependencies and the built wheel
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir /wheel/*.whl && \
    rm -rf /wheel

# Expose the port your application uses
EXPOSE 8080

# Launch the application
CMD ["python", "client/runClient.py"]

