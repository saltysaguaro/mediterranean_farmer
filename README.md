# Mediterranean Farm Pages Repo

This folder is meant to become the lightweight GitHub repository for the public web app.

## What lives here

- `docs/`: the GitHub Pages publish root
- small repo metadata and publishing instructions

Large raw, processed, and intermediate climate datasets stay in the parent project so the public repo remains focused on the interactive site.

## Refresh the site

Build directly into `docs/` from the parent project:

```bash
PYTHONPATH=src python3 -m mediterranean_farm.cli run --config config/pipeline.github-pages.toml
```

If you already have a generated site in `outputs/webapp`, sync it into this folder:

```bash
PYTHONPATH=src python3 -m mediterranean_farm.cli prepare-github-repo
```

## Publish with GitHub Pages

1. Initialize this `github_repo/` folder as its own Git repository.
2. Push it to GitHub.
3. In the GitHub repository settings, enable Pages from the `main` branch and `/docs` folder.
