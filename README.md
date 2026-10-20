# VirtualCloset

A local Python / Streamlit class demo: private accounts, batch clothing uploads,
automatic FashionCLIP recognition, a persistent virtual closet, and today's outfit.
No paid API keys are required. Presentation, shopping links and virtual try-on are outside this version.

## Open and run

Extract this folder to a NEW location, for example `E:\MyFile\Codiing\Python\VirtualClosetDemo`.
Do not extract over your old project or move its virtual environment.
Open the extracted folder containing `app.py` in PyCharm.

On Dylan's current computer, double-click `Start_VirtualCloset.bat` to launch.
It uses this project's `.venv` if available, otherwise the existing E: project interpreter,
otherwise `python` on PATH. No source-file editing is needed.

You can reuse your existing interpreter:
`E:\MyFile\Codiing\Python\VirtualCloset\.venv\Scripts\python.exe`

From the new folder's terminal run:

```powershell
& 'E:\MyFile\Codiing\Python\VirtualCloset\.venv\Scripts\python.exe' -m streamlit run app.py
```

Stop the previous app with Ctrl+C first if port 8501 is occupied.
The application opens at http://localhost:8501. Register your own account; there is no preset password.
The first account automatically receives the three previously saved demo clothes from
`data/legacy_closet.db`. Other accounts start empty. The legacy snapshot is retained as a backup.
Initial recommendation for imported clothes computes the missing embeddings automatically.

## Fresh installation

Python 3.13 on Windows, tested with RTX 3060. In PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File .\setup_windows.ps1
powershell -ExecutionPolicy Bypass -File .\run_windows.ps1
```

The setup script creates a local `.venv` and installs PyTorch 2.9.1 / torchvision 0.24.1
from the CUDA 12.6 wheel index, then the pinned application dependencies.
CPU inference is supported but slower. CUDA is selected when available.
Model weights are downloaded from Hugging Face on first use and cached outside this project.
The existing Hugging Face cache on this computer is reused. The ZIP does not contain model weights.

## Use

1. Create an account or log in.
2. Add clothes: select multiple photos and click Add to closet. Use one garment per image.
3. My closet shows your saved thumbnails. Attributes remain internal.
4. Today's outfit: choose an occasion, optionally include a coat/jacket, and request a suggestion.
5. Add more tops/bottoms/shoes to see meaningful alternatives. The original three garments yield
   one top-bottom combination, with an optional coat; the app explicitly reports this limitation.
6. Remove an item through its confirmation control. Removal only affects the signed-in account.

## Structure

- `app.py`: user interface / entry point
- `virtual_closet/auth.py`: password hashing and validation
- `virtual_closet/database.py`: users, owned items, migration, CRUD
- `virtual_closet/model.py`: pretrained FashionCLIP inference and embeddings
- `virtual_closet/attributes.py`: prompt vocabulary
- `virtual_closet/recommendation.py`: occasion retrieval and outfit assembly
- `virtual_closet/images.py`: validation, orientation, thumbnails
- `virtual_closet/config.py`: paths and model settings
- `scripts/`: model, attribute, and database inspection commands
- `tests/`: account isolation, migration, and recommendation checks
- `data/`: runtime SQLite database and legacy snapshot
- `picture/sample_pics/`: your three sample images

Paths are resolved from the project folder, not the terminal's current directory.
Set `VIRTUALCLOSET_DATA_DIR` to override the data directory (used for isolated tests).

## Database

`users`: id, unique normalized username, password_hash, created_at.

`clothing_items`: id, user_id (foreign key), filename, image_hash, image_data,
attributes_json, rankings_json, embedding_json, model_id, model_version, created_at.

Images are resized JPEG BLOBs; originals on your disk are not changed. Attributes and normalized
image embeddings are stored internally as JSON. UNIQUE(user_id,image_hash) prevents exact-file
duplicates per user; edited/re-encoded photos are not detected as duplicates. Foreign keys are
enabled on every connection. All app item operations include the authenticated user's ID.

## What is learned and what is not

The app really runs `patrickjohncyh/fashion-clip` pretrained weights with PyTorch.
It encodes each image once, compares its embedding with text prompt embeddings, and stores
the three highest-ranked labels per attribute. These rankings are not calibrated probabilities.
Adding labels does not retrain the model. The model can mistake coat types, logos and colors;
it does not detect/crop multiple garments or reject every non-clothing photo.

Outfit recommendation is a hybrid demo, inspired by Loom's category-slot retrieval approach:

- FashionCLIP image/text cosine similarity measures relevance to the chosen occasion.
- Candidate slots are top + bottom OR dress, with shoes when present and an optional outer layer.
- At most eight model-ranked items per slot enter candidate enumeration.
- Candidate score = mean occasion cosine + 0.04 * simple color heuristic
  - 0.02 * max(0, number of non-solid pieces - 1).
- The color heuristic counts equal-color pairs or pairs containing a neutral color.
- Up to three options rotate within the five highest-ranked candidates by local date and button clicks.

These heuristics and weights are application design choices, not published FashionCLIP results.
Semantic similarity is NOT proof of outfit compatibility. This demo does not train on user behavior,
run FGAT, predict fit, use live weather, or claim scientifically evaluated recommendation quality.

## Research and references

- Chia et al. (2022), *Contrastive language and vision learning of general fashion concepts*,
  Scientific Reports 12, 18958. https://doi.org/10.1038/s41598-022-23052-9
- FashionCLIP code: https://github.com/patrickjohncyh/fashion-clip
- Weights: https://huggingface.co/patrickjohncyh/fashion-clip
  The repository describes the later FashionCLIP 2.0 update; do not present the 2022 paper's
  results as an evaluation of this app or of every later checkpoint.
- Loom: https://github.com/anushreeberlia/loom — architecture inspiration only; this is an
  independent small implementation, not a copy of its full stack or its Fashion Florence service.
- FGAT: https://github.com/sajjadsaed/FGAT — related research reviewed; no FGAT checkpoint is
  bundled or executed here. Paper: https://doi.org/10.1016/j.mlwa.2025.100802

## Testing and inspection

Run from the project root using the selected Python interpreter:

```powershell
python -m unittest discover -s tests -v
python -m scripts.test_model
python -m scripts.test_attributes
python -m scripts.inspect_database
```

Manual demo checks: register A, upload a batch, repeat the same batch, log out, register B,
verify B has an empty closet, log back in as A, request an outfit, and remove a test item.
Account and recommendation tests use disposable databases; they never modify your real closet.

## Local-demo boundaries

Passwords use salted PBKDF2-HMAC-SHA256 (600,000 iterations) and constant-time comparison.
Login has a session-level retry delay. This is not production authentication: no password reset,
email verification, durable rate limiting, HTTPS deployment, or persistent login cookies.
It binds to localhost by default. Anyone with filesystem access can read the database;
account separation is application-level, not database encryption. Browser refresh may log you out.

No attribute editing is exposed to users. The app stores predictions automatically, as requested.
The first-account legacy import is intended only for this single-computer migration, not a public signup flow.

## GitHub

`.gitignore` excludes databases (including the legacy backup), virtual environments, caches,
and the sample retailer images. Do not force-add those files. The personal delivery ZIP includes
your sample data for continuity; public source can run with an empty closet and your own images.
Model weights and sample images retain their respective upstream terms. No automatic publishing is performed.
