# Google credentials guide

`unical` talks to Google Calendar through an OAuth client that **you** own, so
your calendar data never goes through anyone else's app. This guide creates
that client step by step. You do it once; it's free and takes about five
minutes.

```
Google Cloud project ──▶ Calendar API ──▶ consent screen ──▶ Desktop OAuth ──▶ credentials.json
   (step 1)               enabled          + you as a        client ID          imported by
                          (step 2)         test user         (step 4)           unical (step 5)
                                           (step 3)
```

> [!NOTE]
> Google renames and moves things in the Cloud Console from time to time. The
> links below go straight to each page; if a menu name differs, follow the link.
> In newer consoles the consent screen settings live under
> **Google Auth Platform** (pages **Branding**, **Audience** and **Clients**)
> instead of **APIs & Services → OAuth consent screen**.

## Before you start

Pick the Google account to use. It's simplest to use the account that owns (or
can see) your calendars. If that's a university account and it can't create
projects, see [University Google accounts](#university-google-accounts).

## 1. Create a project

1. Open the [project creation page](https://console.cloud.google.com/projectcreate).
2. Give it any name, for example `unical`, and press **Create**.
3. Make sure the new project is selected in the project picker at the top of
   the page before going on. Every following step applies to the selected
   project.

## 2. Enable the Google Calendar API

1. Open the [Google Calendar API page](https://console.cloud.google.com/apis/library/calendar-json.googleapis.com).
2. Press **Enable**.

Without this step, login works but every sync fails with an error saying the
API has not been used in the project or is disabled.

## 3. Configure the OAuth consent screen

1. Open the [OAuth consent screen](https://console.cloud.google.com/apis/credentials/consent).
   If asked, press **Get started**.
2. Fill in the app information: any app name (e.g. `unical`) and your email as
   the support and developer contact address.
3. For the user type (**Audience**), choose **External**.
4. Finish the wizard. You don't need to add scopes here: `unical` asks for the
   Calendar permission itself when you log in.
5. Add yourself as a test user. Under **Test users** (on the **Audience** page
   in newer consoles), press **Add users** and enter the Google address you'll
   log in with.

> [!IMPORTANT]
> **Don't skip the test user.** The app stays in **Testing** mode, where only
> listed test users may log in. Anyone else is stopped by Google with
> `Error 403: access_denied` ("Access blocked: … has not completed the Google
> verification process"). You don't need to publish or verify the app.

While the app is in Testing mode, Google expires the login after about a week.
`unical` then simply opens the browser to log in again.

## 4. Create the OAuth client ID

1. Open the [Credentials page](https://console.cloud.google.com/apis/credentials)
   (or **Clients** in newer consoles).
2. Press **Create credentials → OAuth client ID** (or **Create client**).
3. As the application type, choose **Desktop app**. Any name works.
4. Press **Create**, then **Download JSON**. The file is called something like
   `client_secret_1234-abcd.apps.googleusercontent.com.json`.

> [!WARNING]
> Choose **Desktop app**. A **Web application** client fails at login with
> `redirect_uri_mismatch`, and a **service account** key doesn't work at all:
> `unical` rejects it when you import it.

Keep this file private: anyone who has it can pose as your app.

## 5. Give the file to unical

The easiest way is to just run `unical`. When there are no credentials yet, it
explains what's needed and asks for the path of the file: paste it, or drag and
drop the file onto the terminal. The file is copied to your user configuration
directory (e.g. `~/.config/unical` on Linux).

To import it ahead of time instead:

```bash
unical auth import /path/to/client_secret_….json
```

Then log in and check that everything is in place:

```bash
unical auth login
unical auth status
```

Your browser opens on Google's login page. Because the app is unverified,
Google shows a warning: press **Continue** (it's your own app), then allow
access to your calendars. The login is saved to `token.json`, so you only do
this again when it expires.

## University Google accounts

Many universities run Google Workspace with restrictions that block creating
Cloud projects or OAuth clients, or using unverified third-party apps.

- **Can't create the project or client?** Do steps 1–4 with a personal
  `@gmail.com` account instead. The project owner and the account you log in
  with don't need to be the same: add the account you'll log in with as a test
  user in step 3.
- **Blocked when logging in with the university account?** Your
  university's admin doesn't allow unverified apps, and there's no way around
  that on your side. Log in with a personal account instead and give the tool
  your timetable from there: subscribe to the university calendar in that
  account, or use its [iCal URL](../README.md#use-an-ical-url-as-the-source).

## Troubleshooting

| Problem                                           | Fix                                                                                    |
| ------------------------------------------------- | -------------------------------------------------------------------------------------- |
| `Error 403: access_denied` in the browser         | Add the account you log in with under **Test users** (step 3).                         |
| `redirect_uri_mismatch` in the browser            | The client is not a **Desktop app**. Create a new one (step 4).                        |
| `This file is a Google Cloud Service Account key` | You downloaded a service account key. Create an **OAuth client ID** instead (step 4).  |
| Sync fails: Calendar API not enabled              | Enable the Google Calendar API in the same project as the client (step 2).             |
| Login asked again every week                      | Expected while the app is in Testing mode. Log in again; nothing else needs to change. |

More problems are listed in the README's
[troubleshooting section](../README.md#troubleshooting).
