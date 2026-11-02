# Image preprocessing

Phone photos and scans are tilted, uneven in lighting and noisy. `intellidoc/preprocess.py`
cleans the image before OCR:

1. **Grayscale.** Colour is noise for OCR.
2. **Resize.** Small images are scaled up (shortest side to about 2000 px) and huge ones capped (3200 px), because Tesseract works best at a consistent character size.
3. **Deskew.** The tilt is estimated with a projection profile (rotate through small angles and keep the angle where text lines are sharpest), and corrected if it is between 0.4 and 10 degrees.
4. **Denoise.** `fastNlMeansDenoising`.
5. **Adaptive threshold.** Black text on white, even under uneven lighting.

## Modes

`--preprocess auto` (default) OCRs both the raw and the cleaned image and keeps the read with the
higher Tesseract word confidence. `on` and `off` force one path.

## Measured effect

On `samples/sample_pan_noisy.png` (tilted, blurred, noisy, with a lighting gradient):

| | OCR confidence | Result |
|---|---|---|
| Raw image | about 19 | fields missing |
| Preprocessed | about 95 | all fields extracted and validated |

The automated test `test_preprocessing_rescues_a_degraded_photo` asserts a gain of more than 20
points. Preprocessing is not always better: on clean scans it can slightly hurt, which is why
`auto` exists.
