FROM python:3.11-slim-bullseye
WORKDIR /app
COPY requirements.txt /src/
RUN pip install -r /src/requirements.txt
COPY spotify_playlist_sync.py /src
CMD ["python3", "/src/spotify_playlist_sync.py", "-d", "--add", "-e"]
