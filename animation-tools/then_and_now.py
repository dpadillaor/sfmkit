"""The README's opening figure: the historical photograph beside a modern one."""

import cv2
import numpy as np

HEIGHT, GAP = 400, 8

old = cv2.imread("data/valencia/scene/Img_Old.jpg")
new = cv2.imread("data/valencia/scene/Img01.jpg")
old, new = (cv2.resize(i, (round(i.shape[1] * HEIGHT / i.shape[0]), HEIGHT),
                       interpolation=cv2.INTER_AREA) for i in (old, new))
gap = np.full((HEIGHT, GAP, 3), 255, np.uint8)
cv2.imwrite("website/docs/figures/then_and_now.jpg", np.hstack([old, gap, new]),
            [cv2.IMWRITE_JPEG_QUALITY, 88])
