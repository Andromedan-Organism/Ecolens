
![Ecolens Logo](https://github.com/TherealArithmeticProgression/Ecolens/blob/master/0219380b-9c04-4815-a3ac-596a5c762b17.png)

# EcoLens 


A Manifest V3 browser extension with a Python/FastAPI backend for finding openly licensed images and reviewing their reuse details.

## Load in Chrome or Edge

1. Open the browser's extensions page and enable Developer mode.
2. Choose **Load unpacked** and select this folder.
3. Configure and deploy the backend using the steps below, then load the extension unpacked.
4. Enter an image prompt, choose Openverse, Wikimedia Commons, or both, then select **Search selected sources**.
5. Select two results to compare their appearance, dimensions (when provided), and license details.
6. Open the source and license terms before reuse; copy the provided attribution when needed.

## Privacy

Searching sends the entered prompt and selected source names to the EcoLens backend hosted on Render, which forwards the prompt to those sources. The backend does not persist prompts. Source preferences are stored locally by the browser extension. A small pattern-based check runs locally and may warn about a few common personal details. It is not a safety check: it can miss sensitive text or image context, and a clean result does not mean a prompt is safe to share.

The impact panel counts only results the user explicitly marks as reused instead of generating. It estimates 2.907 Wh per marked reuse from the mean image-generation inference energy reported by [Luccioni et al. (ACM FAccT 2024)](https://arxiv.org/abs/2311.16863), then estimates about 0.87 g CO2e using the study's AWS us-west-2 grid intensity of 297.6 g CO2e/kWh. This gross research-based proxy does not subtract EcoLens search/network energy or embodied hardware impacts; it is not a measurement of EcoLens use or an individual user's actual avoided emissions. Results vary by model, hardware, image settings, and electricity mix. The reuse count is stored locally in the extension.

The extension requests access to the EcoLens API and browser local storage. It does not read chat pages. The backend uses the Openverse API and Wikimedia Commons' MediaWiki API; it does not scrape source websites. Wikimedia results are limited to CC0, public-domain, CC BY, and CC BY-SA records with license metadata. Always verify the original license page before reuse. Openverse offers anonymous API access subject to rate limits. See [Openverse API docs](https://api.openverse.org/v1/), [Openverse authentication and throttling](https://docs.openverse.org/api/reference/authentication_and_throttling.html), [Wikimedia Commons API: Search](https://www.mediawiki.org/wiki/API:Search), and [API: Imageinfo](https://www.mediawiki.org/wiki/API:Imageinfo).

## Python backend and OOP design

- `ImageSearchProvider` defines the abstract `search` contract (abstraction) in `backend/app/providers.py`.
- `OpenverseImageSearchProvider` and `WikimediaCommonsImageSearchProvider` inherit that contract and implement it (inheritance).
- `ImageSearchService` calls selected implementations through the shared interface, so it does not depend on a concrete provider (polymorphism).
- Provider clients and the service's provider mapping use underscore-prefixed, internal-by-convention attributes; callers use their public methods. `ImageResult` is the validated, normalized metadata boundary (encapsulation).

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

The focused tests cover local privacy warnings, API response handling, license and attribution details, duplicate or overlapping searches, provider behavior, source selection, partial source failures, and API validation.

## User validation

No user study has been run yet. Test the extension with people who create images for real tasks. Ask them to find a suitable image, explain its license and attribution obligations in their own words, and decide whether they would use it instead of generating an image. Record task completion, time, license comprehension, image choice, and reasons for rejecting a result. Do not treat stated preference alone as evidence of avoided generation.
