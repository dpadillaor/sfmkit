FROM python:3.11-slim

WORKDIR /app

# Installing dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copying and Installing sfmkit library
COPY pyproject.toml .
COPY src src
RUN pip install --no-cache-dir --no-deps .

# The commit this image was built from, recorded in every run manifest
ARG GIT_COMMIT=unknown
ENV SFMKIT_GIT_COMMIT=$GIT_COMMIT

# Entrypoint
ENTRYPOINT ["sfmkit"]
CMD ["--help"]