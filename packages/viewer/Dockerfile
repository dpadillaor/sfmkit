FROM python:3.11-slim

WORKDIR /app

# Installing dependencies
COPY packages/viewer/requirements.txt .
RUN pip install --no-cache-dir --no-deps -r requirements.txt

# Copying and Installing viewer library
COPY packages/viewer/pyproject.toml .
COPY packages/viewer/src src
RUN pip install --no-cache-dir --no-deps .

ENV SFMVIEW_HOST=0.0.0.0
EXPOSE 8000

# Entrypoint
ENTRYPOINT ["sfmview"]
