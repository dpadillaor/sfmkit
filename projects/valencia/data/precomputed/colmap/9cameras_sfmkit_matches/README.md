# COLMAP model: 9 cameras, sfmkit matches

**The names here are the course's**, from before the photographs were
renumbered; `../../../README.md` has the table. `Img00` is `Img_Old`,
`Img02` is `Img01`, and `Img28` was dropped from the set.

COLMAP's mapper run on keypoints and matches it was given, not on its own: the
reconstruction alone, from the same kind of input sfmkit uses. It is what
`colmap.matches: sfmkit` is meant to reproduce.

How it was made, with the COLMAP command-line program:

1. SuperPoint + LightGlue keypoints and matches, RANSAC inliers, from the
   pipeline sfmkit grew out of. Pairs with `Img02` only (a star, not every pair).
2. `database_creator`, `feature_importer`, `matches_importer --match_type inliers`
   (taken as already verified), `mapper`, `model_converter --output_type TXT`.

It registers 10 images, the 9 modern ones and `Img00`, with 2176 points. COLMAP
calibrated the cameras itself (f = 3047 for the phone, against 3544 from the
chessboard).
