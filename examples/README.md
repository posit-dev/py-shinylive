# Example workflows

- [`deploy-app`](#deploy-app) - Deploy a Shiny app to GitHub Pages.

## Deploy App

Reusable workflow that will deploy the root Shiny app dir to GitHub Pages.

The agreed upon contract is:

- Install Python and the `shinylive` package
- Export the Shiny app in the root directory to `./site`
- On push events, deploy the exported app to GitHub Pages

Your app's own dependencies do not need to be installed by the workflow. They
are read from the app's `requirements.txt` at export time and installed in the
browser by Pyodide.

If this contract is not met or could be easily improved for others, please open
a new Issue https://github.com/posit-dev/py-shinylive/ .

To add the workflow to your repository, copy
[`deploy-app.yaml`](deploy-app.yaml) to `.github/workflows/deploy-app.yaml`:

```bash
mkdir -p .github/workflows
curl -fsSL https://raw.githubusercontent.com/posit-dev/py-shinylive/actions-v1/examples/deploy-app.yaml \
  -o .github/workflows/deploy-app.yaml
```

Then, in your repository's Settings > Pages, set the "Source" to "GitHub
Actions".

### Inputs

| Input | Default | Description |
| ----- | ------- | ----------- |
| `python-version` | `""` | Python version used to run `shinylive export`. Empty lets uv pick. |
| `shinylive-version` | `"shinylive"` | Version spec for the `shinylive` package, e.g. `shinylive==0.8.0`. |

# Contributing

If any changes are made to the reusable workflows in `.github/workflows/`, please force update the tag `actions-v1` to the latest appropriate git sha. This will allow users to easily reference the latest version of the workflow.

```bash
git tag -f actions-v1
git push --tags --force
```

This update is not necessary for changes in `examples/` as these files are copied within each of the user's repositories.
