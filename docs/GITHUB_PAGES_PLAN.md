# Plan: SportSQL project page on GitHub Pages (username.github.io/SportSQL)

## Goal
- Have a **single, polished project page** (like the Map&Make example) at **https://coral-lab-asu.github.io/SportSQL/** (or your username/org).
- That page should be what visitors see **instead of** the raw README when they open the repo’s GitHub Pages URL.

---

## How GitHub Pages works for project sites

For a **project site** (not a user/org site):

- URL: `https://<owner>.github.io/<repo>/` (e.g. `https://coral-lab-asu.github.io/SportSQL/`).
- You can either:
  1. **Use the `main` branch and the `/docs` folder** (recommended here), or  
  2. Use a dedicated `gh-pages` branch (root of that branch = site root).

Recommended: **Source = Branch: `main`, Folder: `/docs`**.  
Then:
- `docs/index.html` → served as the site’s **index** (this will be your new “blog-like” page).
- Any file in `docs/` is served at `/<filename>` (e.g. `docs/paper.pdf` → `.../SportSQL/paper.pdf`).
- So the new landing page is **only** `docs/index.html` (and its assets); the README in the repo root is unchanged and still shows on the GitHub repo tab.

---

## Content and structure of the new page

Model the layout and style on the Map&Make page you shared, adapted to SportSQL.

### 1. **Hero**
- Title: **SportSQL: Interactive System for Real-Time Sports Reasoning and Visualization**
- Authors (from README/paper): Naman Ahuja, Fenil Bardoliya, Chris Bryan?, Vivek Gupta, etc. (align with ACL Anthology).
- Venue: **IJCNLP 2025 (Demo)**.
- Buttons: **Paper** (ACL Anthology), **Code** (GitHub), **Demo** (link to live demo if any), **Dataset/DSQABENCH** (if you have a link).

### 2. **Teaser**
- One hero image (e.g. `screenshot.png` or a diagram of the pipeline).
- Short tagline: e.g. “Natural language to SQL and visualizations over live Fantasy Premier League data.”

### 3. **Abstract**
- Use the abstract from the ACL/IJCNLP paper, or the short description from the README.

### 4. **Introduction**
- 1–2 short paragraphs: problem (NL over sports data), approach (NL2SQL + deep research + visualization), and why it’s useful.

### 5. **Key features / system**
- **Three query modes**: Single-Query NL2SQL, Deep Research, Interactive Visualization (with 1-line descriptions and example questions).
- **Architecture**: Real-time FPL data, temporal DB, LLM (Gemini/OpenAI), PostgreSQL, modular design (reuse README bullets).

### 6. **DSQABENCH**
- Short description: 1,700+ queries, SQL programs, gold answers, DB snapshots, diverse query types. Link to dataset if hosted (e.g. Hugging Face / Zenodo / GitHub).

### 7. **Example queries**
- Simple, Deep Research, and Visualization example queries (from README).

### 8. **Screenshots / results** (optional)
- Screenshot of the web UI, and optionally 1–2 result tables or charts (reuse from `website/static/` or `viz-static-site/` if useful).

### 9. **Documentation / quick start**
- Very short “Quick start” (clone, env, DB setup, run website) with link to **README** or **docs/LOCAL_SETUP.md** for full instructions.

### 10. **Citation (BibTeX)**
- Full BibTeX from the paper (README already has a version; use the final ACL Anthology one).

### 11. **Footer**
- License, acknowledgments (FPL API, Gemini/OpenAI, PostgreSQL, CORAL Lab), optional “Page template from …” if you reuse Nerfies/Map&Make style.

---

## File and asset layout (under `docs/`)

So that the new page is self-contained and works when GitHub serves from `/docs`:

```
docs/
├── index.html              # Single-page project site (Map&Make-style)
├── static/                 # Assets for the project page only
│   ├── css/
│   │   └── (bulma or minimal CSS + custom styles)
│   ├── js/
│   │   └── (optional, e.g. smooth scroll / nav)
│   └── images/
│       ├── hero.png        # Teaser (e.g. copy or symlink screenshot.png)
│       └── (any other figures you add)
├── LOCAL_SETUP.md          # Keep existing
├── LLM_USAGE.md            # Keep existing
├── Dynamic_Sports_QA.pdf   # Keep existing
└── GITHUB_PAGES_PLAN.md    # This file (optional to keep after setup)
```

- In `index.html`, reference assets with **relative paths** from `docs/`, e.g.:
  - `./static/css/main.css`
  - `./static/images/hero.png`
- Because the site root URL is `.../SportSQL/`, these paths will resolve to `.../SportSQL/static/...` and work correctly.

---

## Styling (Map&Make-like)

- Reuse the same approach as the Map&Make page:
  - **Bulma** (via CDN or from `static/css/bulma.min.css`) for layout and components.
  - **Google Fonts**: e.g. Google Sans, Noto Sans.
  - Same kind of **inline or linked custom CSS**: hero, section padding, link color, button hover, smooth scroll.
- Keep it **one single HTML file** (plus optional one main CSS file in `static/css/`) so the page is easy to maintain and fast to load.
- Favicon: optional; can point to repo favicon or a small logo in `static/images/`.

---

## Steps to implement

1. **Create `docs/static/`**  
   - `docs/static/css/`, `docs/static/js/` (if needed), `docs/static/images/`.

2. **Add assets**  
   - Copy or symlink `screenshot.png` → `docs/static/images/hero.png` (or similar).  
   - Add Bulma (and any other CSS/JS) under `docs/static/` or via CDN in `index.html`.

3. **Write `docs/index.html`**  
   - One HTML file that includes:
     - All sections above (Hero, Teaser, Abstract, Introduction, Features, DSQABENCH, Examples, Screenshots, Quick start, BibTeX, Footer).
     - Links and paths relative to `docs/` (e.g. `./static/...`).
     - Meta tags, title, and optional Open Graph for sharing.

4. **Enable GitHub Pages**  
   - Repo → **Settings → Pages**.  
   - **Source**: “Deploy from a branch”.  
   - **Branch**: `main`, **Folder**: `/docs`.  
   - Save. After a few minutes, the site will be at `https://<owner>.github.io/SportSQL/`.

5. **Optional**  
   - In README, add at the top: “🌐 **Project page**: [https://coral-lab-asu.github.io/SportSQL/](https://coral-lab-asu.github.io/SportSQL/)”.  
   - So people who land on the repo can quickly jump to the nice page.

---

## Summary

| Item | Choice |
|------|--------|
| **URL** | `https://<owner>.github.io/SportSQL/` |
| **Source** | Branch `main`, folder `/docs` |
| **Landing page** | `docs/index.html` (new, Map&Make-style) |
| **Assets** | `docs/static/` (css, images, optional js) |
| **README** | Unchanged; optional link to project page at top |

Result: visiting `.../SportSQL/` shows the new project page; the README stays the default view on the GitHub “Code” tab.
