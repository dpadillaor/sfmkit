FROM python:3.11-slim

WORKDIR /app

# PyTorch and COLMAP depending on device.
ARG DEVICE=cpu
# COLMAP's CUDA build links X11 libraries the slim image lacks.
RUN if [ "$DEVICE" = gpu ]; then \
        apt-get update \
        && apt-get install -y --no-install-recommends libice6 libsm6 libx11-6 libxext6 \
        && rm -rf /var/lib/apt/lists/*; \
    fi
COPY packages/sfmkit/requirements-${DEVICE}.txt .
RUN pip install --no-cache-dir --no-deps -r requirements-${DEVICE}.txt

# Installing dependencies
COPY packages/sfmkit/requirements.txt .
RUN pip install --no-cache-dir --no-deps -r requirements.txt

# NN Weights
ENV TORCH_HOME=/opt/torch
RUN python -c "from lightglue import LightGlue, SuperPoint; SuperPoint(); LightGlue(features='superpoint')"

# Valencia example: photos, configs and a saved run
COPY data/valencia data/valencia
COPY configs/valencia configs/valencia
COPY examples/valencia/9cameras runs/valencia/9cameras

# Copying and Installing sfmkit library
COPY packages/sfmkit/pyproject.toml .
COPY packages/sfmkit/src src
RUN pip install --no-cache-dir --no-deps .

# The commit this image was built from, recorded in every run manifest
ARG GIT_COMMIT=unknown
ENV SFMKIT_GIT_COMMIT=$GIT_COMMIT

# Entrypoint
ENTRYPOINT ["sfmkit"]
CMD ["--help"]
