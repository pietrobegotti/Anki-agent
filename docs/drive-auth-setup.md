# Google Drive authorization setup

The Windows worker uses an installed-app OAuth client. Google issues a short-
lived access token for API calls and a refresh token for future runs. The
refresh token is stored with the operating system credential store through
Python `keyring`; it is not written into Drive or the repository.

## Create the OAuth client

1. In Google Cloud Console, create or select a project.
2. Enable the Google Drive API for that project.
3. Configure the OAuth consent screen for your Google account. Add the
   `https://www.googleapis.com/auth/drive.file` scope.
4. Create an OAuth client ID with application type **Desktop app** and download
   its JSON file.
5. Copy that file to
   `<ANKI_AGENT_DATA_DIR>/<ANKI_AGENT_USER_ID>/google-oauth-client.json`.
   With default settings this is `collection_docs/default/google-oauth-client.json`.
   This is local configuration and must not be committed or shared.

For a personal or testing OAuth application, add your Google account as a test
user if Google's consent screen requires it. Google may show an unverified-app
notice while the application is in testing.

## Authorize the worker

Install dependencies, then run this once on the PC that will import cards:

```powershell
uv sync --locked
uv run anki-agent drive-auth
```

The command opens Google consent in the browser and asks for access to files
created by or explicitly shared with Anki Agent. After approval, the refresh
token is saved in the Windows credential store. No token is printed. If
authorization is revoked, run `drive-auth` again.

The worker creates its folders under `My Drive/Anki Agent/`. To place the
folder under a different Drive parent, set `ANKI_AGENT_DRIVE_PARENT_ID` to a
folder that the OAuth app can access. For the least setup, leave this unset and
use the Drive root.

## ChatGPT connection

The ChatGPT side needs its own Google Drive connection or a deployed custom
app that can write the approved JSON request into `Anki Agent/queue/`. This is
separate OAuth consent: the worker's local refresh token is never shared with
ChatGPT. The ChatGPT account and interface must support Drive write actions for
the user to save queue files from both desktop and phone.
