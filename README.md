# Elhosari Barber CRM (Django)

## Local setup
1. `python3 -m venv .venv`
2. `source .venv/bin/activate`
3. `pip install -r requirements.txt`
4. `python manage.py migrate`
5. `python manage.py createsuperuser`
6. `python manage.py runserver`

## What is scaffolded
- Custom user model with roles: owner/admin, receptionist, barber
- Permission toggle model for owner-controlled access changes
- Core domain models: clients, services, appointments, and audit logs
- Arabic/English multilingual setup with English default and RTL support
- Server-rendered base UI with custom CSS and brand logo integration
- Working M2 screens: clients, service catalog, appointments, and walk-ins
- Audit logging signals for create/update/delete on core business models

## AI Playground provider config
Set these environment variables before running the server to enable real AI image generation in `AI Playground`.
`config/settings.py` auto-loads values from a root `.env` file when present.

- `AI_PLAYGROUND_PROVIDER`: `nanobanana`, `grok`, `replicate_hairclip`, `hf_hairfastgan`, or `stub`
- `AI_PLAYGROUND_PROVIDER_TIMEOUT_SECONDS`: request timeout in seconds
- `AI_PLAYGROUND_MAX_IMAGE_SIZE_BYTES`: upload size limit
- `AI_PLAYGROUND_SESSION_GENERATION_LIMIT`: max generation attempts per QR session
- `AI_PLAYGROUND_MIN_GENERATE_INTERVAL_SECONDS`: cooldown between generation attempts in one session
- `AI_PLAYGROUND_START_MAX_PER_IP_PER_HOUR`: max QR session starts per IP per hour
- `AI_PLAYGROUND_GENERATE_MAX_PER_IP_PER_HOUR`: max generation requests per IP per hour
- `AI_PLAYGROUND_ONE_STYLE_PER_SESSION`: `1` to allow each curated style once per session
- `AI_PLAYGROUND_DATA_RETENTION_HOURS`: retention window before cleanup removes stale data

Nanobanana (Gemini image API):
- `AI_PLAYGROUND_NANOBANANA_API_KEY`
- `AI_PLAYGROUND_NANOBANANA_MODEL` (default: `gemini-2.5-flash-image`)
- `AI_PLAYGROUND_NANOBANANA_ENDPOINT` (optional override)
- `AI_PLAYGROUND_NANOBANANA_IMAGE_SIZE` (optional: `1K`, `2K`, `4K`)
  - If unset, `gemini-3-pro-image-preview` is forced to `1K` output to minimize output-token cost.
- Prompt set toggles for fast A/B testing:
  - `AI_PLAYGROUND_NANOBANANA_PROMPT_SET` (global default; valid values: `1`, `2`, `3`, `4`, `5`; default: `1`)
  - `AI_PLAYGROUND_NANOBANANA_FLASH_PROMPT_SET` (optional flash-only override)
  - `AI_PLAYGROUND_NANOBANANA_PRO_PROMPT_SET` (optional pro-only override)
  - Set meaning:
    - `1`: balanced replacement (default)
    - `2`: aggressive visible-change enforcement
    - `3`: shorter direct prompt
    - `4`: staged replacement prompt
    - `5`: concise flash-first haircut replacement prompt
- Cost estimates are auto-detected by model for:
  - `gemini-2.5-flash-image` (input `$0.30` / output `$30.00` per 1M tokens)
  - `gemini-3-pro-image-preview` (input `$2.00` / output `$120.00` per 1M tokens)
- `AI_PLAYGROUND_NANOBANANA_INPUT_COST_PER_1M_TOKENS` and `AI_PLAYGROUND_NANOBANANA_OUTPUT_COST_PER_1M_TOKENS` are only used as fallback for unknown/custom model IDs.

Grok images:
- `AI_PLAYGROUND_GROK_API_KEY`
- `AI_PLAYGROUND_GROK_MODEL` (default: `grok-2-image`)
- `AI_PLAYGROUND_GROK_IMAGES_ENDPOINT` (default: `https://api.x.ai/v1/images/edits`)
- `AI_PLAYGROUND_GROK_IMAGE_FORMAT` (default: `base64`)

Replicate HairCLIP (test-gated):
- `AI_PLAYGROUND_REPLICATE_HAIRCLIP_ENABLED`: must be `1` to allow provider use
- `AI_PLAYGROUND_PROVIDER=replicate_hairclip`
- `AI_PLAYGROUND_REPLICATE_API_TOKEN` (required)
- `AI_PLAYGROUND_REPLICATE_API_BASE` (default: `https://api.replicate.com/v1`)
- `AI_PLAYGROUND_REPLICATE_HAIRCLIP_MODEL_VERSION` (default: `b95cb2a16763bea87ed7ed851d5a3ab2f4655e94bcfb871edba029d4814fa587`)
- `AI_PLAYGROUND_REPLICATE_HAIRCLIP_FALLBACK_HAIRSTYLE` (default: `short hair hairstyle`)
- `AI_PLAYGROUND_REPLICATE_HAIRCLIP_WAIT_SECONDS` (default: `60`; max supported by Replicate sync wait is 60)
- `AI_PLAYGROUND_REPLICATE_HAIRCLIP_POLL_INTERVAL_SECONDS` (default: `2`)
- `AI_PLAYGROUND_REPLICATE_HAIRCLIP_MAX_IMAGE_SIDE` (default: `1024`)
- `AI_PLAYGROUND_REPLICATE_HAIRCLIP_JPEG_QUALITY` (default: `90`)
- HairCLIP provider currently edits hairstyle/color only (no beard edit path).

Suggested `.env` block for HairCLIP:
```env
AI_PLAYGROUND_PROVIDER=replicate_hairclip
AI_PLAYGROUND_REPLICATE_HAIRCLIP_ENABLED=1
AI_PLAYGROUND_REPLICATE_API_TOKEN=r8_xxxxxxxxxxxxxxxxxxxxx
AI_PLAYGROUND_REPLICATE_API_BASE=https://api.replicate.com/v1
AI_PLAYGROUND_REPLICATE_HAIRCLIP_MODEL_VERSION=b95cb2a16763bea87ed7ed851d5a3ab2f4655e94bcfb871edba029d4814fa587
AI_PLAYGROUND_REPLICATE_HAIRCLIP_FALLBACK_HAIRSTYLE=short hair hairstyle
AI_PLAYGROUND_REPLICATE_HAIRCLIP_WAIT_SECONDS=60
AI_PLAYGROUND_REPLICATE_HAIRCLIP_POLL_INTERVAL_SECONDS=2
AI_PLAYGROUND_REPLICATE_HAIRCLIP_MAX_IMAGE_SIDE=1024
AI_PLAYGROUND_REPLICATE_HAIRCLIP_JPEG_QUALITY=90
```

Hugging Face HairFastGAN (test-gated):
- `AI_PLAYGROUND_HF_HAIRFASTGAN_ENABLED`: must be `1` to allow provider use
- `AI_PLAYGROUND_PROVIDER=hf_hairfastgan`
- `AI_PLAYGROUND_HF_HAIRFASTGAN_SPACE` (default: `AIRI-Institute/HairFastGAN`)
- `AI_PLAYGROUND_HF_HAIRFASTGAN_TOKEN` (optional, recommended for rate limits/private spaces)
- `AI_PLAYGROUND_HF_HAIRFASTGAN_ALIGN` (default: `Face,Shape,Color`)
- `AI_PLAYGROUND_HF_HAIRFASTGAN_BLENDING` (default: `Article`; options: `Article`, `Alternative_v1`, `Alternative_v2`)
- `AI_PLAYGROUND_HF_HAIRFASTGAN_POISSON_ITERS` (default: `0`)
- `AI_PLAYGROUND_HF_HAIRFASTGAN_POISSON_EROSION` (default: `15`)
- `AI_PLAYGROUND_HF_HAIRFASTGAN_SWAP_MAX_RETRIES` (default: `3`, retries transient upstream swap errors)

Suggested `.env` block:
```env
AI_PLAYGROUND_PROVIDER=hf_hairfastgan
AI_PLAYGROUND_HF_HAIRFASTGAN_ENABLED=1
AI_PLAYGROUND_HF_HAIRFASTGAN_SPACE=AIRI-Institute/HairFastGAN
AI_PLAYGROUND_HF_HAIRFASTGAN_TOKEN=
AI_PLAYGROUND_HF_HAIRFASTGAN_ALIGN=Face,Shape,Color
AI_PLAYGROUND_HF_HAIRFASTGAN_BLENDING=Article
AI_PLAYGROUND_HF_HAIRFASTGAN_POISSON_ITERS=0
AI_PLAYGROUND_HF_HAIRFASTGAN_POISSON_EROSION=15
AI_PLAYGROUND_HF_HAIRFASTGAN_SWAP_MAX_RETRIES=3
```

Cleanup task:
- `python manage.py cleanup_ai_playground --retention-hours 24`
- `python manage.py cleanup_ai_playground --dry-run`
