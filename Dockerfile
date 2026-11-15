# Same Python version as the Windows development machine (3.12).
FROM python:3.12-slim

WORKDIR /app

# No .pyc files inside the image; print output immediately (no buffering).
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install dependencies first: this layer is cached and rebuilt only when requirements.txt changes.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Then the code, keyword rules, sample data and tests (see .dockerignore for what is left out).
COPY . .

# `docker run IMAGE file.csv` == `python -m ticket_organizer file.csv`.
# Without arguments the program starts in interactive mode (needs `docker run -it`; start.sh does this).
ENTRYPOINT ["python", "-m", "ticket_organizer"]
