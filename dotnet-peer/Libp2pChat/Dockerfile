# Build stage
FROM mcr.microsoft.com/dotnet/sdk:8.0-alpine AS builder

WORKDIR /usr/src/app

# Copy csproj and restore dependencies
COPY Libp2pChat.csproj ./
RUN dotnet restore

COPY . .


RUN dotnet publish -c Release -o /app/publish

FROM mcr.microsoft.com/dotnet/aspnet:8.0-alpine

# Install required packages for Terminal.Gui
RUN apk add --no-cache \
    bash \
    ncurses \
    ca-certificates \
    && adduser -D appuser

# Create dir & add permissions
RUN mkdir -p /app/data && \
    chown -R appuser:appuser /app

# Copy the published application from builder
COPY --from=builder /app/publish /app/

# Set working directory
WORKDIR /app/data

# Use non-root user
USER appuser

# Set env vars
ENV TERM=xterm-256color
ENV LANG=C.UTF-8
ENV DOTNET_SYSTEM_CONSOLE_ALLOW_ANSI_COLOR_REDIRECTION=1

# Expose port
EXPOSE 9050

# Run the application
ENTRYPOINT ["dotnet", "/app/Libp2pChat.dll"] 