# Release Checklist

Use this before publishing a GitHub release.

## Before Push

- Confirm `.env`, `cookies.txt`, and `data/` are not tracked.
- Run `python -m compileall .`.
- Update `CHANGELOG.md`.
- Update the version/tag in the GitHub release notes.
- Check `README.md` setup commands still match the project layout.

## Suggested First Release

```bash
git init
git add .
git commit -m "Initial Discord VPS bot release"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
git push -u origin main
git tag v1.0.0
git push origin v1.0.0
```

Then create a GitHub release from tag `v1.0.0` and attach `discord-vps-bot.zip` if you want a downloadable archive.

