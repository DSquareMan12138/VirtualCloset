# VirtualCloset

A local wardrobe app built with Python and Streamlit. Upload clothing photos, review their details, organize your closet, and generate outfit suggestions from clothes you own.

## Features

- Separate user accounts and closets; new accounts start empty.
- Batch photo uploads with background removal before attribute recognition.
- Review each photo beside its editable name, brand, and category before saving.
- Searchable brand selector with alphabetical brands, Other, and custom text entry.
- Category filters, saved item names, renaming, and batch removal with confirmation.
- Per-account background color applied to clothing cutouts in closet and outfit views.
- Up to three distinct outfit suggestions, with clothes displayed in a row per suggestion on desktop.
- Occasion, optional mood/style, optional jacket or coat, and Refresh controls.

## Installation and launch

Run commands from the project folder containing `app.py`. Use a Python environment with PyTorch installed. The included Windows setup script targets Python 3.13 and CUDA 12.6 wheels; GPU support depends on compatible hardware and drivers.

### Existing environment / PyCharm

Select your project's Python interpreter, then run in its activated terminal:

```powershell
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

`requirements.txt` does not install PyTorch. If your environment does not already have it, install a PyTorch build suitable for your computer before launching.

### Included Windows setup

```powershell
powershell -ExecutionPolicy Bypass -File .\setup_windows.ps1
powershell -ExecutionPolicy Bypass -File .\run_windows.ps1
```

`setup_windows.ps1` creates `.venv`, installs PyTorch and torchvision, and installs the app dependencies. Once set up, `Start_VirtualCloset.bat` launches the app through `run_windows.ps1`.

The current launcher prefers the project's `.venv`, then tries an author-specific interpreter path, then `python` on PATH. A project-local `.venv` avoids relying on that fallback.

Open the local URL printed in the terminal, normally `http://localhost:8501`. Stop the server with Ctrl+C.

The first model use requires internet access to download weights. Later runs reuse cached weights. No paid inference API or additional model training is required; computation runs on your computer.

## Using the app

1. Register an account or log in.
2. In Add clothes, select photos and click Analyze photos.
3. Review the cutout, name, brand, and category. Click Add to closet above or below the batch.
4. In My closet, filter by category, rename items, or select multiple items for removal.
5. In Today's outfit, choose your preferences and click Suggest outfits. Use Refresh for alternatives.

Use one garment per photo. Supported upload types are JPG, JPEG, PNG, and WebP, limited to 20 MB and 24 megapixels per image.

Brands are entered by the user, not detected by FashionCLIP. Leaving the brand unselected, or entering only whitespace under Other, stores an empty brand as SQL NULL and displays Unknown / No brand.

Default names combine brand when supplied, color, and subcategory, with fallbacks. Users can override names before saving or rename saved items. Custom categories remain in the closet but are excluded from outfit generation.

## Image processing and performance

Upload processing follows this order:

1. Check for an identical uploaded file in the current account or batch.
2. Remove the background using rembg.
3. Composite the cutout onto white for FashionCLIP analysis.
4. Show the review screen, then save only after Add to closet is clicked.

Original upload bytes and transparent cutouts are stored separately. The selected display color does not affect recognition. Existing items without cutouts can be processed using Remove backgrounds from existing clothes.

rembg uses the smaller `u2netp` model on CPU by default. Set `VIRTUALCLOSET_REMBG_MODEL=u2net` before launching to use the larger model, trading processing time for a potentially different cutout quality.

FashionCLIP uses CUDA when available, otherwise CPU. Models and text features are reused; display previews are resized and cached. Switching the main tabs does not request a server rerun, although other interactive controls can. First-time downloads and model loading can still take time, and batch photos are analyzed sequentially.

## Recommendation approach

The recommender is an independent local Loom-inspired adaptation. It does not install or run the upstream Loom application or a pretrained Loom outfit model.

FashionCLIP compares stored image embeddings with the requested occasion and mood. The app combines these relevance scores with simple color and pattern heuristics to sample outfits. Suggestions have equal status in the UI; their numbers are labels, not quality rankings.

Supported combinations are top + bottom or dress, with shoes when available and an optional jacket or coat. If shoes are missing, results are labeled as clothing-only. Refresh favors combinations outside the immediately previous set when enough alternatives exist. Fewer than three combinations, or unavoidable repeats, are explained in the interface.

Very large closets use a maximum of 100,000 sampled candidate combinations. Recommendation quality has not been established by a formal evaluation; visual similarity and heuristic coordination do not guarantee a good outfit.

## Project files

| Path | Purpose |
| --- | --- |
| `app.py` | Streamlit interface and application entry point |
| `requirements.txt` | Application dependencies; PyTorch installed separately |
| `.streamlit/config.toml` | Streamlit configuration |
| `virtual_closet/auth.py` | Username validation and password hashing |
| `virtual_closet/config.py` | Data paths and FashionCLIP settings |
| `virtual_closet/database.py` | Accounts, clothing records, migrations, and saved preferences |
| `virtual_closet/attributes.py` | Attribute labels and prompts |
| `virtual_closet/model.py` | FashionCLIP inference and embedding comparisons |
| `virtual_closet/images.py` | Image validation, cutouts, and background compositing |
| `virtual_closet/brands.py` | Brand directory |
| `virtual_closet/metadata.py` | Naming and reviewed metadata handling |
| `virtual_closet/recommendation.py` | Outfit combinations and weighted sampling |
| `tests/` | Automated regression tests |
| `scripts/` | Optional model and database diagnostics |
| `data/closet.db` | Current SQLite database |
| `picture/sample_pics/` | Optional photos for the attribute diagnostic script |
| `setup_windows.ps1` | Windows environment setup |
| `run_windows.ps1` / `Start_VirtualCloset.bat` | Windows launch helpers |

Keep package `__init__.py` files. Keep the main directories in place unless the corresponding paths and imports are updated.

## Database and Git

The default database is `data/closet.db`. Set `VIRTUALCLOSET_DATA_DIR` before launching to use another data directory. Paths otherwise resolve relative to the project, not the terminal's working directory.

The database contains two tables: `users` and `clothing_items`. It stores accounts, password hashes, background preferences, clothing names, brands, attributes, embeddings, original images, and cutouts. Images are inside the database; the app does not require the original upload files afterward.

The app creates a database if one is absent and adds supported columns to a compatible existing database. An older incompatible schema raises an error; legacy databases are not automatically imported.

This project may include a deliberately shared demonstration database. To include the default database while keeping other data ignored, put this exception after the existing ignore patterns:

```gitignore
!data/closet.db
```

Close the running app before making a database snapshot or committing it. Keep virtual environments, caches, secrets, logs, and SQLite temporary files out of Git. A database committed to Git is a snapshot, not a shared live database.

## Tests and diagnostics

```powershell
python -m unittest discover -s tests -v
```

Optional diagnostics:

```powershell
python -m scripts.test_model
python -m scripts.test_attributes
python -m scripts.inspect_database
```

Model diagnostics require downloaded weights and the inference dependencies. The attribute script reads `picture/sample_pics/` directly and does not exercise the app's background-removal upload flow. Database inspection requires an existing initialized database.

## Scope and limitations

- This is a local demonstration, not a production authentication or hosting system.
- Accounts separate data through the application; the database itself is not encrypted.
- FashionCLIP selects labels from configured candidates. Predictions and cutouts can be wrong.
- Brand recognition, virtual try-on, shopping links, live weather, and feedback-based learning are not implemented.
- Narrow screens may stack columns instead of showing all clothing images on one line.
- A browser refresh may require signing in again.

## Components

- FashionCLIP model identifier: `patrickjohncyh/fashion-clip`
- Background removal: `rembg`
- Interface: Streamlit
- Storage: SQLite
- Recommendation: local Python combination generation and weighted sampling
