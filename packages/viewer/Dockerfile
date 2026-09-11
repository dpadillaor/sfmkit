FROM python:3.11-slim

WORKDIR /app

# Installing dependencies
COPY packages/viewer/requirements.txt .
RUN pip install --no-cache-dir --no-deps -r requirements.txt

# Copying and Installing viewer library
COPY packages/viewer/pyproject.toml .
COPY packages/viewer/src src
RUN pip install --no-cache-dir --no-deps .

# Inside a container, listen on every address: a published port arrives on
# the container's network address, not on its loopback
ENV SFMVIEW_HOST=0.0.0.0
EXPOSE 8000

# Asks /api/health from inside; set the port with SFMVIEW_PORT, not --port,
# so the check finds it too
HEALTHCHECK --interval=10s --timeout=3s --retries=3 --start-period=10s --start-interval=1s \
    CMD ["sfmview-health"]

# Entrypoint
ENTRYPOINT ["sfmview"]
