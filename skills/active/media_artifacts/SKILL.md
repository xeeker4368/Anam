---
name: media_artifacts
description: Find existing media artifacts and generate ordinary image/media artifacts when chat image generation is explicitly enabled.
version: "1.0"
---

# Media Artifacts

Use these tools for explicit user requests involving generated or uploaded media artifacts.

- Use `media_search` to find generated or uploaded media by title, artifact id, description, prompt, or provenance metadata.
- Use `media_get` to inspect safe artifact metadata for a specific artifact id.
- Use `image_generate` only when the user explicitly asks to create or generate an image. It creates ordinary generated media/reference artifacts only and may be disabled by configuration.

Boundaries:

- Do not use these tools to create or assign identity, name, or self-representation.
- Generated images are ordinary media artifacts, not identity facts.
- Tool results return safe metadata and preview URLs only, never raw image bytes.
