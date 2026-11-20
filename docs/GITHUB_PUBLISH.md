# Operator-controlled GitHub export

This tool intentionally **does not connect GitHub to the AI model** and cannot push code on its own.

1. Install Git and GitHub CLI (`gh`) on Windows; authenticate `gh auth login`, configure `git config --global user.name` and `user.email`.
2. Review all source files and the QA report. Ensure the project is `completed` and the target repository belongs to you.
3. Run a **dry-run**:

```powershell
py -3 scripts\publish-github.py 0123456789abcdefabcd --repo OWNER/REPOSITORY
```

4. Only after you approve, run the same command with `--publish`. You must type an exact confirmation phrase. A **new branch** named `wfs/<id>-<timestamp>` will be pushed, source placed under `wfs-deliveries/<id>/`, and `gh pr create --draft` will be requested. No forced push, no merge and no GitHub Pages publication are performed.

The result depends on your repository permissions and PR settings; **GitHub publication has not been tested** in this build environment. Be mindful of potential sensitive content AI may generate, even though automatic credential-pattern checks exist.
