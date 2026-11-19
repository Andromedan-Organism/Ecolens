
![Ecolens Logo](https://github.com/TherealArithmeticProgression/Ecolens/blob/master/0219380b-9c04-4815-a3ac-596a5c762b17.png)

# EcoLens 


A Manifest V3 browser extension with a Python/FastAPI backend for finding openly licensed images and reviewing their reuse details.

## Load in Chrome or Edge

1. Open the browser's extensions page and enable Developer mode.
2. Choose **Load unpacked** and select this folder.
3. Configure and deploy the backend using the steps below, then load the extension unpacked.
4. Enter an image prompt and choose **Search Openverse**.
5. Select two results to compare their appearance, dimensions (when provided), and license details.
6. Open the source and license terms before reuse; copy the provided attribution when needed.

## Privacy

Pressing **Search Openverse** sends the entered prompt to the EcoLens backend hosted on Render, which forwards it to Openverse. The backend does not persist prompts. A small pattern-based check runs locally and may warn about a few common personal details. It is not a safety check: it can miss sensitive text or image context, and a clean result does not mean a prompt is safe to share.

The extension requests host access only to the EcoLens API. It does not read chat pages. The backend calls Openverse's search API and does not scrape source websites. Openverse offers anonymous API access subject to rate limits. See [Openverse API docs](https://api.openverse.org/v1/) and [authentication and throttling](https://docs.openverse.org/api/reference/authentication_and_throttling.html).

## Python backend and OOP design

- `ImageSearchProvider` is an abstract interface for image providers (abstraction).
- `OpenverseImageSearchProvider` inherits that interface and implements its search operation (inheritance).
- `ImageSearchService` accepts the interface and delegates searching to the provider without depending on the concrete class (polymorphism).
- Provider and service state is kept behind their methods, and `ImageResult` is the normalized data boundary (encapsulation).

### Deploy to Render

The API is live at [https://ecolens-8mvu.onrender.com](https://ecolens-8mvu.onrender.com), with its health check at [https://ecolens-8mvu.onrender.com/health](https://ecolens-8mvu.onrender.com/health). The extension is configured to use this service.

To deploy it yourself, connect this repository in Render and create a Python web service using the settings in `render.yaml`. You can create the service manually; using a Render Blueprint is optional.

The API is public and has no user authentication in this MVP. CORS is not authentication; use provider-side rate limits/monitoring and add an access-control strategy before treating this as a production service. Render's free service may sleep when idle, so the first search after a quiet period can take longer.

## Tests

Run `npm test` with Node.js. On Windows, create a Python virtual environment and run the backend tests with:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m unittest discover -s backend\tests
```

The focused tests cover local privacy warnings, API response handling, license and attribution details, duplicate or overlapping searches, provider behavior, and API validation.

## User validation

No user study has been run yet. Test the extension with people who create images for real tasks. Ask them to find a suitable image, explain its license and attribution obligations in their own words, and decide whether they would use it instead of generating an image. Record task completion, time, license comprehension, image choice, and reasons for rejecting a result. Do not treat stated preference alone as evidence of avoided generation.
