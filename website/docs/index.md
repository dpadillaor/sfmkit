---
hide:
  - navigation
  - toc
---

<section class="sfm-panel" markdown>
<div class="sfm-panel__head">sfmkit <span class="num">v0.1.0</span></div>
<div class="sfm-panel__body" markdown>

<h1 class="sfm-wordmark">sfmkit</h1>
<p class="sfm-tagline">structure from motion · tested library · live 3d viewer</p>

<p class="sfm-lead">A small, tested Structure-from-Motion library — two-view
geometry, feature tracks, incremental reconstruction and bundle adjustment. It
rebuilds a place in 3D from modern photographs, places an old photograph in
that model, and checks itself against <a href="https://colmap.github.io/">COLMAP</a>.</p>

<div class="sfm-cta" markdown>
[Tutorial](tutorial.md){ .md-button .md-button--primary }
[Install](install/conda.md){ .md-button }
[Results](project/results.md){ .md-button }
</div>

</div>
</section>

<section class="sfm-panel">
<div class="sfm-panel__head">valencia / cpu <span class="num">saved example</span></div>
<dl class="sfm-metrics">
<div><dt>cameras</dt><dd>14</dd></div>
<div><dt>points</dt><dd>2 850</dd></div>
<div><dt>mean rotation error</dt><dd class="signal">0.338<span class="unit">°</span></dd></div>
<div><dt>old photo error</dt><dd>1.32<span class="unit">°</span></dd></div>
</dl>
</section>

![The same square, a century apart](figures/then_and_now.jpg)

*Plaza de la Virgen, Valencia. Left: an undated historical photograph. Right: the
same square today, from a phone.*

**Where was the old photograph taken from, and what has changed since?**

sfmkit answers that from a handful of modern photographs of the same place:

1. **It rebuilds the place in 3D** from the modern photographs, and works out
   where each of them was taken from. The technique is called *Structure from
   Motion*.
2. **It uses the old photograph**: places it in that 3D model, recovering where
   it was taken from even though its camera is unknown, and overlays it on a
   modern photograph to show what has changed.
3. **It checks itself** against COLMAP, the standard tool for the job, and says
   how far apart the two answers are.

<video controls muted loop playsinline width="100%">
  <source src="figures/old_photo.mp4" type="video/mp4">
</video>

## Start here

<div class="grid cards" markdown>

- **[Tutorial](tutorial.md)** — from a clone to a reconstruction you can turn
  around, then the same on photographs of your own.
- **[Install](install/conda.md)** — three conda environments, or
  [Docker](install/docker.md) and nothing on the host.
- **[The pipeline](guide/pipeline.md)** — the ten stages, and how the
  reconstruction is actually built.
- **[CLI reference](guide/cli.md)** — every command and every option, with
  [the configuration](guide/config.md) that drives them.
- **[The viewer](viewer/index.md)** — both models in 3D, live while a run is
  built, with its [HTTP API](viewer/api.md) and
  [message format](viewer/live.md).
- **[Results](project/results.md)** — the numbers, the 11.5° argument, and what
  a bundle adjustment of our own bought.
- **[Development](project/development.md)** — the layering, the checks, and CI.
- **[Questions](faq.md)** — COLMAP, GPUs, the weights, and why the old
  photograph is handled apart.

</div>

## In one command

```bash
sfmkit run --config configs/valencia/cpu.yaml   # every stage, in order
sfmview --runs runs                             # look at what it made
```

The viewer shows a run's two models side by side, each in its own colour —
<span class="sfm-dot amber"></span>sfmkit in amber,
<span class="sfm-dot blue"></span>COLMAP in blue — and the old photograph
located against them.
