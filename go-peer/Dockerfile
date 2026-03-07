# Use a specific version of golang alpine for better reproducibility
FROM golang:1.25-alpine AS builder

WORKDIR /usr/src/app

# pre-copy/cache go.mod for pre-downloading dependencies
COPY go.mod go.sum ./
RUN go mod download && go mod verify

# Copy the source code
COPY . .

# Build the application with security flags
RUN CGO_ENABLED=0 go build -ldflags="-w -s" -v -o /usr/local/bin/universal-chat-go ./...

# Create a minimal production image
FROM alpine:latest

# Add CA certificates for HTTPS and create non-root user
RUN apk --no-cache add ca-certificates && \
  adduser -D appuser

# Create a directory for the application and set proper permissions
RUN mkdir -p /app/data && \
  chown -R appuser:appuser /app

# Copy the binary from builder
COPY --from=builder /usr/local/bin/universal-chat-go /usr/local/bin/universal-chat-go

# Set working directory
WORKDIR /app/data

# Use non-root user
USER appuser

# Expose port if your application needs it (uncomment and adjust if needed)
EXPOSE 9050

CMD ["universal-chat-go", "--headless"]
