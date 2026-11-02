# Validation with Pydantic

Extraction returns raw strings. Pydantic turns them into trusted data or tells us exactly what is
wrong. The models are in `intellidoc/schemas.py` and the registry `SCHEMAS` maps type to model.

## PAN card

- `pan_number`: five letters, four digits, one letter, for example `ABCPV1234K`.
- The 4th letter is the holder type and must be one of `A B C F G H J L P T`. The 4th letter of `ABCPV1234K` is `P`, an individual.
- `dob`: parsed from `dd/mm/yyyy`, `dd-mm-yyyy` or `yyyy-mm-dd` into a real date, so `31/02/1995` is rejected.
- `name` and `father_name`: whitespace and stray punctuation cleaned.
- `holder_type` is a computed field derived from the 4th letter.

## Aadhaar card

- 12 digits, first digit 2-9.
- The last digit must satisfy the **Verhoeff checksum**, the check used for Aadhaar numbers. A single misread digit almost always breaks it, which is exactly the OCR error we want to catch.
- The number is exposed masked (`XXXX XXXX 0124`) in the output and database.

## Research paper

- `title` at least 5 characters.
- `figure_captions` list, `n_figures` count, `has_abstract`, `kpis` (sentences that contain a number and a result word such as "improves" or "reduced").

## What a failure looks like

```
pan_number: 4th character 'X' is not a valid holder type
```

A field that was never found reports `not found in the document`. Either way the document goes to
`handle_error`, is retried if it makes sense, and otherwise lands in the review queue.

## OCR misreads are repaired before validation

OCR confuses look-alike characters (`0`/`O`, `1`/`I`, `5`/`S`, `8`/`B`). Because a PAN has a fixed
shape, `fix_pan_candidate` corrects each position towards the character class it must belong to.
The validator then checks the repaired value, so a repair can never smuggle in an invalid PAN.
