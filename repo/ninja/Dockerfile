# Multi-stage Dockerfile extending shared .NET template

# Build stage - extends shared .NET template
FROM shared/dotnet:9.0 AS build

WORKDIR /src

# Copy solution and project files for dependency caching (project file lives directly under src/)
COPY *.sln global.json* nuget.config* ./
RUN mkdir -p src
COPY src/*.csproj ./src/
RUN dotnet restore --verbosity minimal

# Copy full source and references then build (library project FKS.csproj)
COPY src ./src
COPY references ./references
RUN --mount=type=cache,target=/root/.nuget/packages \
    dotnet build src/FKS.csproj -c Release -o /app/publish \
    --no-restore --verbosity minimal

# Runtime stage - using ASP.NET runtime
FROM mcr.microsoft.com/dotnet/aspnet:9.0 AS final

WORKDIR /app

# Install curl for health checks
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy published application from build stage
COPY --from=build /app/publish .

# Set service-specific environment variables
ENV SERVICE_NAME=fks-ninja \
    SERVICE_TYPE=ninja \
    SERVICE_PORT=8080 \
    ASPNETCORE_ENVIRONMENT=Production \
    ASPNETCORE_URLS=http://+:8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:${SERVICE_PORT}/health || exit 1

EXPOSE ${SERVICE_PORT}

# Create non-root user
ARG USER_ID=1088
RUN groupadd --gid ${USER_ID} appuser \
    && useradd --uid ${USER_ID} --gid appuser --create-home --shell /bin/bash appuser \
    && chown -R appuser:appuser /app

USER appuser

# Library project (no executable). Keep container alive for artifact access.
ENTRYPOINT ["/bin/bash", "-c", "echo 'FKS build image (library) running. Artifact in /app/FKS.dll'; sleep infinity"]
