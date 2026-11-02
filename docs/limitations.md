# Limitations

- The extractors are rule-based and tuned on synthetic samples, not on real card layouts. Real documents will need more patterns and testing.
- Jev reads text only, so classification depends on OCR quality. Embedded images inside PDFs are counted but not captioned or described.
- Handwriting is outside what Tesseract does well; such documents will usually end up in review.
- Jev has not been exercised against the live service from the tests (stubbed only).
- No authentication on the API. It is meant to run locally.
- Real identity documents are sensitive personal data. Only process documents you are entitled to, keep `data/` out of version control, and note that the full Aadhaar number is not shown in output but is present in the extracted text during processing.
