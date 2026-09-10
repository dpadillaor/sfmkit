FROM python:3.11-slim

WORKDIR /app

# PyTorch, the heaviest layer, first: it changes least. TORCH picks the build
# (cpu, or gpu once requirements-torch-gpu.txt exists).
ARG TORCH=cpu
COPY requirements-torch-${TORCH}.txt .
RUN pip install --no-cache-dir --no-deps -r requirements-torch-${TORCH}.txt

# Installing dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Matching: kornia and LightGlue, and the networks' weights, so that match
# needs no download when it runs
COPY requirements-match.txt .
RUN pip install --no-cache-dir --no-deps -r requirements-match.txt
ENV TORCH_HOME=/opt/torch
RUN python -c "from lightglue import LightGlue, SuperPoint; SuperPoint(); LightGlue(features='superpoint')"

# The Valencia example: photos, configs and a saved run
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
