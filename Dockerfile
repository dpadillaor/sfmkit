FROM python:3.11-slim

WORKDIR /app

# PyTorch and COLMAP depending on device.
ARG DEVICE=cpu
COPY requirements-${DEVICE}.txt .
RUN pip install --no-cache-dir --no-deps -r requirements-${DEVICE}.txt

# Installing dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --no-deps -r requirements.txt

# NN Weights
ENV TORCH_HOME=/opt/torch
RUN python -c "from lightglue import LightGlue, SuperPoint; SuperPoint(); LightGlue(features='superpoint')"

# Valencia example: photos, configs and a saved run
COPY data/valencia data/valencia
COPY configs/valencia configs/valencia
COPY examples/valencia/9cameras runs/valencia/9cameras

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
