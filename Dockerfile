FROM astralsh/uv:python3.11-slim

WORKDIR /app

# Enable bytecode compilation
ENV UV_COMPILE_BYTECODE=1

# Copy from the cache instead of linking since it's a container
ENV UV_LINK_MODE=copy

# Install the project's dependencies using the lockfile and pyproject.toml
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

# Then, copy the rest of the application code and install the project
COPY . .
RUN uv sync --frozen --no-dev

# Run the application
CMD ["uv", "run", "spotify_playlist_sync.py", "-d", "--add", "-e"]
