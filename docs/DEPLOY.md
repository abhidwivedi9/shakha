# Putting Shakha on a public URL

This is for the case where **anyone, anywhere** should be able to open the dashboard —
a permanent address, no tunnel running on your laptop, no cost.

## Why this needs multi-user mode

Shakha was written as a personal vault. Sandboxes live at `workspaces/<scenario-id>`
and progress in a single `progress.json`, so on a shared URL two visitors opening the
same scenario would land in **the same repository on disk** and commit over each other.

`--multi-user` fixes that: each browser gets a `shakha_session` cookie, its sandboxes go
to `workspaces/<session>/<scenario-id>`, and its ticks go to `sessions/<session>.json`.
Sessions untouched for 24 hours are reaped, because a free host's disk is small and a
sandbox is rebuilt from the scenario on demand anyway.

The `Dockerfile` passes `--multi-user` for you. Do not remove it from a public deploy.

## Static hosting will not work

Firebase Hosting, GitHub Pages, Netlify and friends serve files; they cannot run a
process. Shakha's whole point is a server executing real `git`. Deploy `web/` to any of
them and the panes will render while every button fails. You need a **container host**.

Firebase specifically *can* do it, but only as Firebase Hosting rewriting to **Cloud
Run** — and Cloud Run wants a billing account. Hence Koyeb below.

## Deploy to Koyeb (free, no card in most cases)

Koyeb's free instance is 512 MB RAM, 0.1 vCPU, 2 GB SSD, one service. Shakha is stdlib
Python plus git, so that is enough.

1. Push this repository to GitHub (it already lives at `abhidwivedi9/shakha`).
2. Sign in at <https://app.koyeb.com> with your GitHub account.
3. **Create Web Service** → **GitHub** → pick the `shakha` repository, branch `main`.
4. Builder: **Dockerfile** (Koyeb detects the one in the repo root).
5. Instance: **Free**. Region: whichever is nearest.
6. Exposed port: **8000**. Koyeb also injects `$PORT`; the `CMD` honours it either way.
7. Deploy. You get `https://<service>-<org>.koyeb.app`, permanently.

Pushing to `main` afterwards redeploys — that is the "git URL" workflow.

### What the free instance costs you

- It **scales to zero after an hour with no traffic**, and cannot be stopped from doing
  so. The next visitor waits roughly half a minute for the container to wake.
- Waking is a fresh container, so **every sandbox and every visitor's progress is gone**.
  For a public teaching demo that is fine — nothing there was meant to be permanent.
- 0.1 vCPU is shared across everyone on the page at once.

If any of that matters, the same image runs unchanged on Render, Fly.io, Cloud Run or
any VPS.

## Think about this before you share the URL

Anyone who opens the page can run the allow-listed binaries (`git`, `ls`, `cat`, `pwd`,
`echo`) and write files, inside the container. There is no shell and the path guard keeps
everything under `workspaces/`, so the blast radius is one disposable container — but it
is still strangers running processes on your dime. If you would rather it were not open
to the world, add a key and hand the link only to people you choose:

```
CMD ["sh", "-c", "python shakhactl.py dashboard --host 0.0.0.0 --port ${PORT} --multi-user --key ${SHAKHA_KEY} --no-open"]
```

then set `SHAKHA_KEY` as a Koyeb environment variable and share
`https://…koyeb.app/?k=<that value>`. Multi-user and the key are independent: the key
decides *who gets in*, multi-user decides *whether they collide once inside*.

## Keeping it on your own machine instead

If the goal was only ever "me, from my phone, anywhere", skip all of this:

```
python shakhactl.py dashboard --share --key
```

plus a Cloudflare tunnel. Same result, nothing hosted, and your real progress file.
