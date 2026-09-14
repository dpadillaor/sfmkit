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

# Where the weights go. They are not baked in: SuperPoint's are Magic Leap's,
# for noncommercial research and not ours to pass on, so the first `match`
# downloads them into whatever is mounted here -- a volume, by compose's
# default -- and whoever runs it takes those terms on themselves. Any user can
# write there: the container runs as the caller, not as root.
ENV TORCH_HOME=/opt/torch
RUN mkdir -p /opt/torch/hub/checkpoints && chmod -R 777 /opt/torch

# The Valencia project: its photographs, its configs, and the frozen run this
# image can reproduce -- the CPU one, or the GPU one with its dense cloud. The
# other frozen run is left out rather than carried for nothing.
ARG EXAMPLE=cpu
COPY projects/valencia/data projects/valencia/data
COPY projects/valencia/configs projects/valencia/configs
COPY projects/valencia/runs/reference-${EXAMPLE} projects/valencia/runs/reference-${EXAMPLE}

# Copying and Installing sfmkit library
COPY packages/sfmkit/pyproject.toml .
COPY packages/sfmkit/src src
RUN pip install --no-cache-dir --no-deps .

# The commit this image was built from, recorded in every run manifest, and as
# a label too: `docker inspect` then says which code is inside, which is the
# only thing that makes a hand-built image as accountable as a CI-built one.
ARG GIT_COMMIT=unknown
ENV SFMKIT_GIT_COMMIT=$GIT_COMMIT
LABEL org.opencontainers.image.title="sfmkit" \
      org.opencontainers.image.description="Structure from Motion: the pipeline and its CLI" \
      org.opencontainers.image.revision="$GIT_COMMIT" \
      org.opencontainers.image.licenses="MIT"

# A plain `docker run` should not be root either. Compose overrides this with
# the caller's own UID so that the runs it writes on a mounted directory belong
# to them; without compose, this is who runs, and /app is theirs to write in.
RUN useradd --create-home --uid 1000 sfmkit && chown -R 1000:1000 /app
USER 1000:1000

# Entrypoint
ENTRYPOINT ["sfmkit"]
CMD ["--help"]
