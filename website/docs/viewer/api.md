# HTTP API

`sfmview` serves a small read-only JSON API under `/api`, and its own page is
the first client of it. Base URL is wherever the viewer listens, by default
`http://127.0.0.1:8000`.

FastAPI describes it in OpenAPI, served at `/docs` and `/redoc`, and the
messages on the live side have their own description in AsyncAPI — see
[Live messages](live.md#the-contract-as-a-file).

Arrays go out **flat** — `[x0, y0, z0, x1, …]` — because that is what a WebGL
buffer wants, and matrices row-major. Coordinates keep OpenCV's axes (x right,
y down, z forward); the page converts to three.js's in one place.

## `GET /api/health`

Liveness, and whether live progress is available at all.

```json
{"status": "ok", "live": true}
```

`live` is `true` when a broker is configured and answers, `false` when one is
configured and does not, and `null` when none is.

## `GET /api/runs`

Every run under the runs directory.

```json
[
  {
    "id": "valencia/gpu-dense",
    "project": "valencia",
    "config": "gpu-dense",
    "stages": ["calibrate", "match", "verify", "reconstruct", "localize",
               "colmap", "dense", "evaluate", "changes", "figures"],
    "updated": "2026-09-12T16:50:18.283605+00:00",
    "metrics": {
      "mean_rotation_error_deg": 0.2998,
      "max_rotation_error_deg": 1.3360,
      "n_cameras": 14,
      "query_rotation_error_deg": 0.6037
    },
    "layers": ["sfmkit", "colmap", "dense"],
    "devices": {"match": "cuda", "colmap": "cuda"},
    "running": false
  }
]
```

| Field | |
|---|---|
| `stages` | the stage directories that exist, so a half-finished run still lists |
| `metrics` | from `evaluate`'s manifest; `null` where a run has none |
| `layers` | what can be drawn: `sfmkit`, `colmap`, `dense` |
| `devices` | stage to `cuda` or `cpu`, for the stages that record one |
| `running` | sfmkit at work on it now, by its heartbeat; `null` without a broker |

## `GET /api/runs/{project}/{config}/scene`

The 3D scene: both models, their cameras, their points, and the 4×4 that puts
each into the shared frame.

```json
{
  "run": "valencia/gpu-dense",
  "reference": "Img01",
  "models": [
    {
      "source": "sfmkit",
      "cameras": [
        {"name": "Img01", "R": [[1,0,0],[0,1,0],[0,0,1]], "t": [0,0,0],
         "K": [[3029,0,2016],[0,3029,1134],[0,0,1]], "size": [4032, 2268], "query": false},
        {"name": "Img_Old", "R": [["…"]], "t": ["…"], "K": [["…"]], "size": [557, 418],
         "query": true}
      ],
      "points": [1.02, -0.31, 4.55, "…"],
      "colors": [122, 118, 109, "…"],
      "to_common": [[1,0,0,0],[0,1,0,0],[0,0,1,0],[0,0,0,1]]
    },
    {"source": "colmap", "…": "the same shape"}
  ],
  "dense": {"url": "/api/runs/valencia/gpu-dense/dense.ply",
            "to_common": [["…"]]},
  "images": "/api/datasets/valencia/images"
}
```

| Field | |
|---|---|
| `reference` | the camera both models are expressed against |
| `cameras[].query` | the localised photograph, drawn apart from the rest |
| `cameras[].K`, `size` | present when known; the query's K is the one estimated for it |
| `points`, `colors` | flat, finite only — JSON has no `NaN`, so points that never triangulated are simply not sent |
| `to_common` | 4×4 row-major, into the scene's shared frame |
| `dense` | `null` unless the run has a cloud |
| `images` | where the photographs are served from, or `null` |

**One frame for two reconstructions.** Each model has its own origin,
orientation and scale. The scene brings them together the way `evaluate` does,
so what is drawn is what is scored: both are expressed in the reference
camera's frame, and COLMAP's is scaled so that the camera `evaluate` used for
scale sits as far from the reference as it does in sfmkit's. The dense cloud,
being COLMAP's, takes COLMAP's transform.

## `GET /api/runs/{project}/{config}/dense.ply`

COLMAP's fused cloud as a binary PLY, served as it is; the browser parses it.
`404` when the run has none.

## `GET /api/datasets/{dataset}/images/{name}`

One source photograph, by dataset and name without extension, e.g.
`/api/datasets/valencia/images/Img01`. Served from the data directory so the
viewer can show a photograph inside its camera's frustum.

## `WS /api/runs/{project}/{config}/live?after=<id>`

Live progress. The first frame is the server's clock:

```json
{"now": "1757701234567-0"}
```

then one frame per stream entry, history first and new ones as they arrive:

```json
{"id": "1757701234789-0", "message": {"v": 1, "kind": "step", "…": "…"}}
```

`message` is exactly the message sfmkit published —
[Live messages](live.md) has every one of them. `after` resumes from an id you
already have.

A refused socket is **accepted and then closed with a code**, because a refusal
before the handshake reaches a browser as a bare HTTP 403 with nothing to read:

| Code | |
|---|---|
| `4404` | no such run |
| `4503` | live progress is off (no broker configured) |

A stream id starts with the milliseconds Redis wrote it at. With the server's
clock from that first frame, the page can tell what happened after it connected
— an `end` that means there are new files to fetch — from history it is merely
replaying, without trusting the browser's clock.

## Errors and safety

`404` for a run, photograph or cloud that is not there. Names are checked as
single path components and a run directory must resolve inside the runs root,
symlinks included: `../` buys nothing.

Everything is read-only. The viewer never writes into a run, and never imports
sfmkit — it reads the files listed in [the contract](index.md#what-the-viewer-reads)
and the messages on the stream, and nothing else.
