# Install with Docker

Three images, one for each thing that runs: the CLI on the CPU, the CLI on a
GPU, and the viewer. `compose.yaml` at the repository root wires them together
with a Redis for live progress.

Nothing is installed on the host beyond Docker itself — no conda, no COLMAP, no
CUDA toolkit (the GPU image still needs the host's NVIDIA driver and the
container toolkit).

!!! info "Published images"
    The images are not on a registry yet. When they are, this page will say
    `docker pull …` and the rest of it stays the same: the commands below build
    the same images locally, and the compose file will take the published tag
    the moment there is one.

    ```bash
    # Coming: nothing to build, just
    # docker pull <registry>/sfmkit:cpu
    # docker pull <registry>/sfmkit:gpu
    # docker pull <registry>/sfmview
    ```

## First, your user

The CLI container writes runs into a mounted directory, so it runs as you
rather than as root. Compose reads that from `.env`:

```bash
make env        # writes UID= and GID= into .env
```

## Build

```bash
make image                    # sfmkit:cpu
make image DEVICE=gpu         # sfmkit:gpu
docker compose build viewer   # sfmview
```

`make image` passes the current commit in as a build argument, and every run
made inside the image records it in its manifest: a result can be traced to the
code that produced it.

## Run the pipeline

```bash
docker compose run --rm cli run --config configs/valencia/cpu.yaml
docker compose run --rm cli-gpu run --config configs/valencia/gpu-dense.yaml
```

`cli` is the entry point `sfmkit`, so everything after the service name is the
command line you would type locally. The service mounts `./data` and
`./configs` read-only and `./runs` writable, so the output lands in the
repository as usual.

Each image ships the example run it can reproduce: `sfmkit:cpu` carries
`runs/valencia/cpu`, `sfmkit:gpu` carries `runs/valencia/gpu-dense` with its
dense cloud. You can open the viewer on them before running anything yourself.

## The feature weights

They are not baked into the image — SuperPoint's licence is for non-commercial
research and not ours to pass on — so the first `match` downloads them into
whatever is mounted at `/opt/torch`. Compose mounts a named volume by default,
so the download happens once:

```bash
docker compose run --rm cli match --config configs/valencia/cpu.yaml
```

To keep them somewhere of your own, point `SFMKIT_WEIGHTS` at a directory:

```bash
SFMKIT_WEIGHTS=$HOME/.cache/torch docker compose run --rm cli match --config ...
```

If they are missing and there is no network, the run stops with the two URLs
and the paths to put them in, not a stack trace.

## The viewer

```bash
docker compose up -d viewer         # http://127.0.0.1:8000
docker compose down                 # stops the viewer and its Redis
```

It mounts `runs/` and `data/` read-only and publishes port 8000 **on the host's
loopback only**. From another machine, tunnel to it:

```bash
ssh -N -L 8000:127.0.0.1:8000 <host>
```

The image listens on `0.0.0.0` inside the container, because a published port
arrives on the container's network address rather than on its loopback, and it
carries its own healthcheck (`sfmview-health`, which asks `/api/health` from
inside; the image has Python, not curl). In a container set the port with
`SFMVIEW_PORT` rather than `--port`, so the healthcheck finds it too.

## Watching a run as it is built

Live progress is a Redis stream that sfmkit writes and the viewer reads;
compose points both at its own `redis` service:

```bash
docker compose up -d viewer                                   # Redis, then the viewer
docker compose run --rm cli reconstruct --config configs/valencia/cpu.yaml
```

Redis publishes no port: the containers find it by name on compose's network
and nothing outside reaches it. Only the viewer depends on it, so
`docker compose run cli` on its own starts no Redis and publishes nothing —
the run goes ahead either way. `down` removes Redis's container and the next
`up` starts an empty one, losing the streams; `stop` keeps them.

## The services

| Service | Image | What it is |
|---|---|---|
| `cli` | `sfmkit:cpu` | the pipeline, CPU only; entry point `sfmkit` |
| `cli-gpu` | `sfmkit:gpu` | the same with CUDA PyTorch and COLMAP; `gpus: all` |
| `viewer` | `sfmview` | the web viewer on port 8000 |
| `redis` | `redis:7-alpine` | live progress, internal to the compose network |

## Publishing an image

The CPU and viewer images are built and pushed by CI on a version tag. The GPU
one is not: CUDA PyTorch and COLMAP's CUDA build do not fit a hosted runner's
disk, so it is built where there is a GPU and published by hand:

```bash
docker login ghcr.io -u <you>     # once, with a token that can write packages
make push DEVICE=gpu
```

`make push` refuses to publish from a working tree with uncommitted changes,
and stamps the commit into the image twice: as `SFMKIT_GIT_COMMIT`, which every
run manifest records, and as an OCI label. So a published image can always be
traced back, whoever built it:

```bash
docker inspect --format '{{index .Config.Labels "org.opencontainers.image.revision"}}' \
  ghcr.io/<owner>/sfmkit:gpu
```

## GPU

The `cli-gpu` service asks for `gpus: all`, which needs NVIDIA's container
toolkit on the host:

```bash
# Debian/Ubuntu, from NVIDIA's repository
sudo apt-get install -y nvidia-container-toolkit
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
docker compose run --rm cli-gpu --help      # should print sfmkit's help
```

Without it the service fails to start; the CPU image does everything except
`dense`, which is GPU-only in COLMAP.
