# The Plaza de la Virgen photographs

`scene/` holds the fourteen modern photographs, `Img01` to `Img14`, and the
undated one, `Img_Old`. Nothing here is ever written by a run.

The numbers used to be the phone's own (`Img02`, `Img11`, `Img12`, …), with
gaps where a photograph had been discarded, and the old one was `Img00`, which
read as just another frame. They were renumbered in capture order on
2026-09-12, so that the set reads as a set and the odd one out is named as
one:

| Now | Was | | Now | Was |
|---|---|---|---|---|
| `Img_Old` | `Img00` | | `Img08` | `Img17` |
| `Img01` | `Img02` | | `Img09` | `Img18` |
| `Img02` | `Img11` | | `Img10` | `Img19` |
| `Img03` | `Img12` | | `Img11` | `Img20` |
| `Img04` | `Img13` | | `Img12` | `Img23` |
| `Img05` | `Img14` | | `Img13` | `Img24` |
| `Img06` | `Img15` | | `Img14` | `Img25` |
| `Img07` | `Img16` | | | |

`Img01` is the reference, as `Img02` was. `Img28` is in neither column: it was
shot with digital zoom, which made its EXIF focal length 17% wrong, and it was
dropped from the set before this renumbering.

`precomputed/` is not ours to renumber. The COLMAP model in
`colmap/9cameras_sfmkit_matches/` came out of the course and names its images
the way the course did; the table above reads it. `precomputed/K.txt` is the
course's chessboard calibration, kept for the same reason.
