# Classification with Jev

Classification decides which extractor and which Pydantic model apply. IntelliDoc uses **Jev**
(TypeSafe AI's classifier) for this step instead of prompting a general LLM.

## Why not an LLM here

The question is a closed choice between a few labels. A purpose-built classifier returns a label
with calibrated probabilities, is cheaper, and gives consistent answers for the same input.

## Labels

`pan_card`, `aadhaar_card`, `research_paper`, `other`.

## Request

`POST https://api.typesafe.ai/v1/systemone` with `Authorization: Bearer <key>` and a body of the
form:

```json
{
  "model": "jev-latest",
  "state": "<document text>",
  "questions": {
    "doc_type": {
      "type": "choice",
      "instructions": "What kind of document is this?",
      "criteria": {"pan_card": "...", "aadhaar_card": "...", "research_paper": "...", "other": "..."}
    }
  }
}
```

The answer is read from `answers.doc_type.choice`, with `confidence` and `probabilities`. Jev reads
**text only**, so images are OCR'd first. That is why classification comes after ingestion.

## Fallback

If `--no-jev` is set, `TYPESAFE_API_KEY` is missing, or the call fails for any reason, the
keyword classifier runs instead (weighted signals such as "permanent account number" for PAN) and
the result carries the warning `Jev unavailable, used keyword classifier (...)`. The result's
`metadata.classifier` says which one produced the label.

!!! note
    The Jev client is covered by tests with a stubbed HTTP call. It has not yet been run against
    the live service, so confirm the response shape with a real key before relying on it.
