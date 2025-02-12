# Use a specific version of golang alpine for better reproducibility
FROM golang:1.23-alpine AS builder

# Create a non-root user for running the application
RUN adduser -D -g '' appuser

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

# Add CA certificates for HTTPS
RUN apk --no-cache add ca-certificates

# Copy the binary from builder
COPY --from=builder /usr/local/bin/universal-chat-go /usr/local/bin/universal-chat-go
COPY --from=builder /etc/passwd /etc/passwd

# Use non-root user
USER appuser

# Expose port if your application needs it (uncomment and adjust if needed)
EXPOSE 9050

CMD ["universal-chat-go"]
