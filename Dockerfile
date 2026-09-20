FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# The living files - packets, keys, transcripts, commons - live on a mounted
# disk, never inside the image.
ENV DATA_DIR=/data

EXPOSE 8080

# One worker, on purpose: the attend subprocess and the file writes must not race.
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "1", "--threads", "4", "--timeout", "600", "hearth:app"]
