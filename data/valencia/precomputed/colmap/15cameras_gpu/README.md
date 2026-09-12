# COLMAP model: the fifteen photographs, COLMAP's own features

What the `colmap` stage produces on this dataset, saved so that the comparison
can be made without COLMAP installed: `colmap.precomputed` copies it instead of
running anything.

It is COLMAP alone — its own SIFT features, its own matching, its own mapper —
on the fourteen modern photographs, with `Img_Old` registered in a second pass
against the finished model, its principal point free. Nothing here comes from
sfmkit, which is the point: it is an independent answer to the same question.

| | |
|---|---|
| Images | 15 (`Img01`–`Img14` and `Img_Old`) |
| Points | 4 618 |
| Made by | `sfmkit colmap --config configs/valencia/gpu-dense.yaml`, 2026-09-12 |
| Machine | COLMAP 3.11 through pycolmap, CUDA feature extraction |

COLMAP reconstructs from scratch every time and its mapper is randomised, so a
model made again will differ a little — the old photograph most, as
`docs/old-photo.md` explains. This copy is therefore also a fixed reference:
scoring against it compares two runs of sfmkit rather than two runs of COLMAP.

`configs/valencia/no-colmap.yaml` is the config that uses it.
