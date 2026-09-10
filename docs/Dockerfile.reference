# syntax=docker/dockerfile:1
#
# NOT YET BUILT OR TESTED. Written on a machine without Docker; treat it as a
# starting point that needs one `docker build` before it can be trusted.
#
# Multi-stage, for two reasons that generalise beyond this project:
#   * build tooling does not travel to the runtime image;
#   * layers are ordered by how often they change, so editing a source file
#     rebuilds seconds rather than reinstalling PyTorch.
#
# The dependency that actually justifies containerising this project is COLMAP:
# a system binary with an unpleasant dependency tree (Ceres, Eigen, Boost,
# FreeImage, Qt, CUDA). Without it the reference model cannot be regenerated.

# ---------------------------------------------------------------- python deps
FROM nvidia/cuda:12.1.1-runtime-ubuntu22.04 AS python-deps

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
        python3.10 python3.10-venv python3-pip \
        libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

ENV VIRTUAL_ENV=/opt/venv PATH="/opt/venv/bin:$PATH"
RUN python3.10 -m venv "$VIRTUAL_ENV"

# Dependencies before source: editing sfmkit must not reinstall torch.
WORKDIR /app
COPY pyproject.toml README.md ./
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --upgrade pip \
 && pip install torch==2.4.1 torchvision==0.19.1 \
        --index-url https://download.pytorch.org/whl/cu121 \
 && pip install "numpy<2" "scipy>=1.11" "opencv-python-headless>=4.8" \
        "matplotlib>=3.7" "rich>=13" "pyyaml>=6" "textual>=0.60" \
 && pip install "lightglue @ git+https://github.com/cvg/LightGlue.git"

# -------------------------------------------------------------------- runtime
FROM nvidia/cuda:12.1.1-runtime-ubuntu22.04 AS runtime

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH" \
    MPLBACKEND=Agg

# COLMAP from the distribution rather than from source: far less to go wrong.
# The packaged build may lag upstream and may be CPU-only; build from source if
# GPU feature extraction is needed, which this pipeline does not use (matching
# is SuperPoint + LightGlue).
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3.10 colmap \
        libgl1 libglib2.0-0 git \
    && rm -rf /var/lib/apt/lists/*

COPY --from=python-deps /opt/venv /opt/venv

WORKDIR /app
COPY pyproject.toml README.md Makefile ./
COPY src/ ./src/
COPY configs/ ./configs/
RUN pip install --no-deps -e .

# Images and run outputs are mounted, never baked in: an image is not a place
# for data, and results must outlive the container.
VOLUME ["/data", "/app/runs"]

ENTRYPOINT ["sfmkit"]
CMD ["--help"]
