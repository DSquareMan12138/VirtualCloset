VirtualCloset replacement files — 2026-10-20

Apply this update
1. Stop Streamlit.
2. Back up your project and data/closet.db (or the directory specified by VIRTUALCLOSET_DATA_DIR).
3. Copy app.py and requirements.txt into your project root.
4. Copy virtual_closet/ files into your existing virtual_closet/ folder.
5. Copy tests/ files into your existing tests/ folder.
6. In your existing activated environment:
   python -m pip install -r requirements.txt
   python -m unittest discover -s tests -v
   python -m streamlit run app.py

Keep your existing auth.py, config.py, model.py, attributes.py, __init__.py, data, and launch scripts.
This package contains no database and does not import legacy data.
The first launch adds columns to the current database while retaining accounts and items.

Included replacement files
- app.py
- requirements.txt
- virtual_closet/database.py
- virtual_closet/images.py
- virtual_closet/recommendation.py
- tests/test_core.py

Included new files
- virtual_closet/metadata.py
- virtual_closet/brands.py
- tests/test_updates.py

Upload
- Choose photos, then Analyze photos.
- rembg removes the background BEFORE FashionCLIP detects attributes.
- FashionCLIP receives a white composite of the cutout, independent of the display theme.
- Review each photo on the left and its name, brand, and category on the right.
- Add to closet buttons appear above and below the reviewed batch.
- Originals and transparent cutouts are stored separately.
- Failed analysis/removal leaves that image unsaved and reports the error.
- Duplicate uploaded images are skipped per account.
- Brand choices use your supplied directory: 256 unique brands, searchable, alphabetical, Other first.
- No selection or blank Other text saves SQL NULL and displays Unknown / No brand.
- Names default to Brand + Color + Subcategory, with Category/Clothing item fallbacks.
- Manual names remain unchanged when brand/category changes.
- Custom categories are saved but excluded from outfit generation.

Closet
- All first, populated categories alphabetical, Uncategorized last.
- Up to six category buttons use one row; larger sets use two balanced rows.
- Names are stored in the database and may be renamed.
- Select all applies to the current category. Switching category clears selection.
- Removing selected items requires confirmation of the count.
- Background color is stored per account and shared by closet and outfit displays.
- Use Remove backgrounds from existing clothes once for older photos; originals remain stored.

Recommendations
- Local Loom-style adaptation using FashionCLIP matching and attribute coordination.
- This does not install upstream Loom or claim to use pretrained Loom outfit weights.
- Occasion and optional mood influence sampling; no outfit ranking or feedback UI.
- Up to three different combinations, presented equally.
- Refresh excludes the immediately previous combinations whenever enough alternatives exist.
- If fewer are available, the interface explains the shortage and any repeats.
- Supports top + bottom + shoes or dress + shoes, optional jacket/coat.
- Without shoes, clothing-only suggestions are clearly labeled.
- Very large combination spaces are sampled with a 100,000-candidate work limit.

Dependencies and validation
- Existing FashionCLIP/PyTorch setup is retained.
- rembg runs on CPU to avoid changing your working CUDA/PyTorch setup.
- The first rembg run downloads its U2Net model; subsequent runs use the local cache.
- No paid API or additional training is used.
- 15 automated tests passed locally: original account checks plus migration,
  owner-scoped operations, names, cutout compositing, upload processing order,
  distinct recommendations and Refresh.
- All included Python files passed syntax checks.
- Real rembg/FashionCLIP inference and the Streamlit UI were not run here:
  those dependencies were unavailable and network installation was blocked.
- Automated upload-order testing uses instrumented image/model boundaries.
- Category layout is designed for desktop; native Streamlit columns may stack on narrow screens.

Sources checked
- https://github.com/danielgatis/rembg
- https://docs.streamlit.io/develop/api-reference/widgets/st.selectbox
- Approach reference: https://github.com/anushreeberlia/loom

