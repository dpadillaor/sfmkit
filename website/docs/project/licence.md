# Licence

The code is under the **MIT licence**: use it, change it, ship it, sell it,
keep the copyright notice. The full text is
[`LICENSE`](https://github.com/dpadillaor/sfmkit/blob/main/LICENSE) in the
repository.

```
Copyright (c) 2026 David Padilla Orenga
```

Four things in or around the repository are not the author's to license, and
[`NOTICE`](https://github.com/dpadillaor/sfmkit/blob/main/NOTICE) says so beside
the licence.

## The photographs

The fourteen modern photographs of the Plaza de la Virgen are the author's own.
`Img_Old`, the undated historical one, is of unestablished authorship; it is
included for the study of the place it shows, and it is the subject of the
project rather than a work redistributed for its own sake.

Your own photographs are, of course, yours. Nothing is uploaded anywhere.

## The feature weights

SuperPoint's weights are Magic Leap's, released **for non-commercial research**,
and LightGlue's come from its own authors. Neither is in this repository nor in
its images: `match` downloads them at first use into whatever `TORCH_HOME`
points at, and whoever downloads them accepts those terms directly.

This is why the images are redistributable at all, and why CI never runs a
stage that would fetch them.

## COLMAP

Called through `pycolmap` by the `colmap` and `dense` stages.
[COLMAP](https://colmap.github.io/) is a separate project under the new BSD
licence, with its own citation requests if you publish work that uses it.

## The fonts and three.js

The viewer vendors IBM Plex Sans and Roboto Mono, both under the SIL Open Font
License 1.1, with the licence text kept beside the files, and three.js, which is
MIT. They are vendored so that the page needs no network, not to claim them.

## Citing this

There is no paper. If you need to point at it, the repository and the commit
are enough — and every run records its own commit in each stage's manifest, so
a figure can name the code that produced it.
