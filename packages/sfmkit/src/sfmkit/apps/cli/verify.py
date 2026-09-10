"""The `sfmkit verify` command."""

from __future__ import annotations

from rich.table import Table

from sfmkit.apps.cli._common import console, progress, run_dir
from sfmkit.data import io
from sfmkit.data.config import load_config


def cmd_verify(args) -> int:
    """Geometric verification: fit a fundamental matrix and keep the inliers."""
    from sfmkit.core.robust import ransac_fundamental

    cfg = load_config(args.config)
    run = run_dir(cfg, args.out)
    src, dst = run / "match", run / "verify"
    files = sorted(src.glob("*.npz"))
    if not files:
        console.print(f"[red]no matches in {src}[/red] -- run `sfmkit match` first")
        return 1

    rows, kept = [], 0
    with progress() as p:
        task = p.add_task("RANSAC", total=len(files))
        for f in files:
            m = io.load_matches(f)
            x0, x1 = m.keypoints0[m.pairs[:, 0]], m.keypoints1[m.pairs[:, 1]]
            res = ransac_fundamental(
                x0, x1, threshold=cfg.sfm.ransac_threshold,
                max_iterations=cfg.sfm.ransac_iterations, seed=cfg.seed,
            )
            ok = res.converged and res.n_inliers >= cfg.sfm.min_inliers
            if ok:
                m.inliers = res.inliers
                io.save_matches(m, dst / f.name)
                kept += 1
            rows.append({
                "pair": f"{m.image0}-{m.image1}", "matches": m.n_matches,
                "inliers": int(res.n_inliers),
                "ratio": round(res.n_inliers / max(m.n_matches, 1), 3),
                "iterations": res.n_iterations, "kept": ok,
            })
            p.advance(task)

    table = Table(title="geometric verification", show_footer=False)
    for c in ("pair", "matches", "inliers", "ratio", "iters", "kept"):
        table.add_column(c, justify="right" if c != "pair" else "left")
    for r in sorted(rows, key=lambda r: -r["inliers"]):
        style = "" if r["kept"] else "dim red"
        table.add_row(r["pair"], str(r["matches"]), str(r["inliers"]), f"{r['ratio']:.2f}",
                      str(r["iterations"]), "yes" if r["kept"] else "no", style=style)
    console.print(table)

    io.write_manifest(run, "verify", cfg, config_path=args.config,
                      extra={"pairs": rows, "n_kept": kept})
    console.print(f"[green]kept[/green] {kept}/{len(files)} pairs -> {dst}")
    return 0
