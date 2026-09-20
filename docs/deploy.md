# Putting the website on finishline.peterparker.ca

The website is `site/`: one static page, its stylesheet, its script and two fonts, written by
`finishline site` from `web/` (the page, in the style of the other project pages on
peterparker.ca), `data/site/results.json` (the measured numbers, written by `finishline
report` in the same run as the README's tables), `data/live.toml`, `data/calendar.json` (the
association's fixture list, so the race picker is the season rather than a hand-kept file) and
the committed prediction files. The runners' predictions are served from `data/predictions/`,
and the runner rows of a race that already ran from `data/retrospect/`; `robots.txt` disallows
both and the host marks both noindex. The page itself names nobody and is indexed. There is no backend, so hosting it is a file upload and one DNS record. It follows the same path as
project 08's `capacity.peterparker.ca` (its `docs/deploy.md`) with one difference: the upload
runs in GitHub Actions on every push, as `peterparker.ca` does, rather than from this machine,
because the prediction week commits a new file every morning and the website has to follow
without anyone at the keyboard.

Steps 1 to 3 are done once, by Peter, in the Azure portal, the Cloudflare dashboard and
GitHub. Step 4 is automatic after that.

## 0. Check the subscription before creating anything

Make sure the Azure CLI is signed in to the subscription the site belongs in; a CLI can
hold more than one login. `<subscription>` and `<resource-group>` below are yours to fill
in.

```powershell
az login
az account set --subscription <subscription>
az staticwebapp list -o table              # the subscription's existing apps
```

## 1. Create the Static Web App

Portal: [Azure Portal](https://portal.azure.com), Create a resource, **Static Web App**
([Microsoft's walkthrough](https://learn.microsoft.com/en-us/azure/static-web-apps/get-started-portal)).

| Setting | Value |
|---|---|
| Subscription | `<subscription>` |
| Resource group | `<resource-group>` |
| Name | `finishline-peterparker-ca` |
| Plan type | **Free** |
| Region | any near you; content is served from a CDN regardless |
| Deployment source | **Other** |

**Choose "Other", not GitHub.** The GitHub option commits a workflow of its own and wires a
credential into the repository. This repository already has its workflow
(`.github/workflows/site.yml`), and the credential goes in GitHub's secret store in step 3,
never in a file.

Or from the CLI:

```powershell
az staticwebapp create --name finishline-peterparker-ca --resource-group <resource-group> `
  --location eastus2 --sku Free --subscription <subscription>
```

A Static Web App serves one set of files to every hostname on it, so this is its own app, not
a second hostname on another site's app.

## 2. The DNS record, at Cloudflare

1. Copy the app's URL from its **Overview** page: `https://<generated-name>.azurestaticapps.net`.
2. In [the Cloudflare dashboard](https://dash.cloudflare.com), open `peterparker.ca`, then
   **DNS**, **Records**, **Add record**:

   | Type | Name | Target | Proxy status | TTL |
   |---|---|---|---|---|
   | CNAME | `finishline` | `<generated-name>.azurestaticapps.net` | **DNS only** | Auto |

3. **Proxy status DNS only, the grey cloud, not the orange one.** A proxied record hides the
   target behind Cloudflare's addresses, Azure's validation cannot see the CNAME, and the
   certificate is never issued. Projects 01 and 08 both hit this.
4. In the Static Web App: **Settings**, **Custom domains**, **+ Add**, **Custom domain on
   other DNS**. Enter `finishline.peterparker.ca`, record type **CNAME**, add
   ([Microsoft's page](https://learn.microsoft.com/en-us/azure/static-web-apps/custom-domain-external)).
   From the CLI instead:

   ```powershell
   az staticwebapp hostname set --name finishline-peterparker-ca --resource-group <resource-group> `
     --hostname finishline.peterparker.ca --subscription <subscription>
   ```

5. Wait for validation, usually minutes, occasionally an hour. Azure issues and renews the
   certificate itself.

## 3. The deploy token and the switch, in GitHub

The workflow uploads with the app's deployment token. It goes into the repository's secret
store straight from the Azure CLI, so it never appears on screen, in a file, in shell history
or in a chat. **The token alone is enough to publish to the site.**

```powershell
az staticwebapp secrets list --name finishline-peterparker-ca --resource-group <resource-group> `
  --subscription <subscription> --query properties.apiKey -o tsv |
  gh secret set AZURE_STATIC_WEB_APPS_API_TOKEN --repo Peter-A-P/finish-line-forecast

gh variable set SITE --body on --repo Peter-A-P/finish-line-forecast
```

Until `SITE` is `on`, every run of the Website workflow skips rather than failing.

## 4. Publish

Automatic from here: every push to `main` rebuilds the site from what is committed and uploads
it, including the prediction week's morning commits. To publish now without a push:

```powershell
gh workflow run site.yml --repo Peter-A-P/finish-line-forecast
gh run watch --repo Peter-A-P/finish-line-forecast
```

## 5. Check it

- Before trusting a change, look at it locally with the host's headers:
  `uv run finishline site` then `uv run finishline serve`, and open <http://localhost:8080>.
  **Not `python -m http.server`**, which sends none of the headers in
  `staticwebapp.config.json` and so shows a page the content security policy would partly
  refuse (project 08 lost a chart on the live site for two weeks that way).
- `https://finishline.peterparker.ca` serves over HTTPS with no certificate warning.
- The browser console on the live page is empty: a policy violation is reported there and
  nowhere else.
- A race page's file hashes match `sha256sum predictions/...` on a fresh clone.

## Two decisions this makes, and why

- **The site can go live while the repository is still private**, unlike GitHub Pages. Do not
  let it: the pages link to the prediction files in the repository as the proof of when each
  was made, and those links do not open for anyone else until it is public. Make the
  repository public first (docs/todo.md), then set `SITE` on.
- **Race pages carry `noindex`** (a meta tag and an `X-Robots-Tag` header), so search engines
  do not list a named person's prediction; the front page, which names nobody, is indexed.
  Reversing it is one line in `publish/site.py` if Peter wants the pages findable.
- **`data/retrospect/` is the same rule for a different thing.** It holds the runner rows of a
  race that ran before this project published anything (PLAN.md 5.9). It is deliberately not
  `data/predictions/`: that directory is the tagged record, and no address should let the two
  be mistaken for each other. Both are disallowed and both are noindex.

Cost: the Free plan, CA$0.
