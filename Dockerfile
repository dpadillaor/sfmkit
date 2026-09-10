FROM python:3.11-slim

WORKDIR /app

# Installing dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copying and Installing sfm library
COPY pyproject.toml .
COPY src src
RUN pip install --no-cache-dir --no-deps .

CMD ["sfmkit", "--help"]
