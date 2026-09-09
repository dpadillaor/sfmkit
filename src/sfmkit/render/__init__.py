"""Figures. The only layer that imports matplotlib.

Kept apart so that nothing in the reconstruction path can open a plot window --
the original scripts were unrunnable headless because plt.show() was scattered
through the geometry code.
"""
