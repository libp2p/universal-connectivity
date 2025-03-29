FROM python:3.9-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libssl-dev \
    libffi-dev \
    python3-dev \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Generate protobuf files
RUN pip install --no-cache-dir protobuf && \
    python -m pip install --no-cache-dir protobuf-compiler && \
    protoc --python_out=. direct_message.proto

# Expose port for libp2p
EXPOSE 9095/tcp
EXPOSE 9095/udp

# Command to run the application
ENTRYPOINT ["python", "main.py"]

# Default arguments
CMD ["--headless"]