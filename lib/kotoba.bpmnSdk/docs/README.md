# @etzhayyim/bpmn-sdk Documentation

This directory contains the GitHub Pages documentation for the @etzhayyim/bpmn-sdk project.

## 📁 Directory Structure

```
docs/
├── index.html          # Main documentation page
├── .nojekyll          # Disables Jekyll processing
├── README.md          # This file
└── api/               # TypeDoc generated API documentation
    ├── index.html     # API documentation entry point
    ├── assets/        # CSS, JS, and other assets
    └── [modules]/     # Individual package documentation
```

## 🚀 GitHub Pages Setup

This documentation is served via GitHub Pages with the following configuration:

- **Source**: Deploy from a branch
- **Branch**: `main`
- **Folder**: `/docs`

### URL

When enabled, the documentation will be available at:
```
https://etzhayyim.github.io/etzhayyim-bpmn-sdk/
```

## 📝 Development

### Adding Content

1. Edit `index.html` for main documentation content
2. Run `pnpm docs` to generate API documentation in `api/` folder
3. Commit and push changes to trigger automatic deployment

### Local Development

To preview the documentation locally:

```bash
# Generate API docs first
pnpm docs

# Serve the docs directory
npx http-server docs -p 8080

# Or using the npm script
pnpm docs:serve
```

### Automated Deployment

The documentation is automatically deployed via GitHub Actions when:

- Code is pushed to the `main` branch
- Files in `packages/`, `typedoc.json`, `README.md`, or the workflow file are modified
- The workflow is manually triggered

The deployment workflow:
1. Builds all packages
2. Generates TypeDoc API documentation
3. Deploys the entire `docs/` directory to GitHub Pages

## 🔧 Configuration

### GitHub Pages Settings

To enable GitHub Pages for this repository:

1. Go to **Settings** → **Pages**
2. Under **Source**, select **Deploy from a branch**
3. Under **Branch**, select **main** and **/docs** folder
4. Click **Save**

### Custom Domain (Optional)

To use a custom domain:

1. Create a `CNAME` file in the `docs/` directory
2. Add your domain name (e.g., `docs.example.com`)
3. Configure DNS settings as per GitHub's documentation

## 📊 Status

- ✅ Basic documentation page created
- ✅ API documentation generation (TypeDoc)
- ✅ Automated deployment pipeline (GitHub Actions)

## 🤝 Contributing

When contributing to documentation:

1. Update `index.html` with new features or changes
2. Ensure all links are working
3. Test locally before committing
4. Follow the existing HTML/CSS structure

## 📞 Support

For questions about the documentation or GitHub Pages setup:

- [GitHub Issues](https://github.com/etzhayyim/etzhayyim-bpmn-sdk/issues)
- [GitHub Discussions](https://github.com/etzhayyim/etzhayyim-bpmn-sdk/discussions)
