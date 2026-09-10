# sfmkit

![The same square, a century apart](docs/figures/then_and_now.jpg)

*Plaza de la Virgen, Valencia. Left: an undated historical photograph. Right: the
same square today, from a phone.*

**Where was the old photograph taken from, and what has changed since?**

sfmkit answers that from a handful of modern photos of the same place:

1. **It rebuilds the place in 3D** from the modern photos, and works out where
   each of them was taken from. The technique is called *Structure from
   Motion* (SfM).
2. **It uses the old photograph**: places it in that 3D model, recovering where
   it was taken from even though its camera is unknown, and overlays it on a
   modern photo to show what has changed.
3. **It checks itself** against [COLMAP](https://colmap.github.io/), the
   standard tool for the job.

## The pipeline

Each step is a command, `sfmkit <stage>`, and `sfmkit run` runs them all in
order.

![The sfmkit pipeline](docs/figures/pipeline.svg)

| Stage | What it does | Valencia example |
|---|---|---|
| `calibrate` | Works out the camera's focal length and image centre, without which nothing can be measured | the phone's calibration |
| `match` | Finds distinctive points in each photo and pairs them up between photos. Runs on a GPU if there is one, about 10× faster; `sfm.device` in the config chooses | 37 photo pairs |
| `verify` | Throws away pairings that do not fit the geometry of two views | `Img02`–`Img13`: 627 of 772 kept |
| `reconstruct` | Builds the 3D model: starts from two photos and adds the rest one at a time | 9 cameras, 1699 points |
| `localize` | Places the old photo in the model | located to within 2 px |
| `colmap` | Gets COLMAP's model of the same photos, to compare against | 10 cameras |
| `evaluate` | Measures how far each camera is from COLMAP's | 0.98° mean error |
| `changes` | Overlays the old photo on a modern one and marks what differs | 7.6% of the overlap |
| `figures` | Draws the plots for a finished run | |

---

*This README is being rewritten for people who want to use the tool. The
previous one, focused on the results, is in [README.old.md](README.old.md).*
