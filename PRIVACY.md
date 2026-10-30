# All Saints — Privacy Policy

This project uses **YouTube API Services**.

_Last updated: October 29, 2026_

All Saints (A.S.†) is a small automated publishing tool run by Luis Bonilla. It researches, produces and posts short videos about Catholic saints to the All Saints accounts on Instagram (@all.holy.saints) and YouTube.

## What the tool accesses
- **YouTube (Google) account of the All Saints channel only.** Using the YouTube Data API, the tool uploads the channel's own videos and reads the channel's basic information (name, handle, subscriber count) to confirm it is connected. The scopes requested are `youtube.upload` and `youtube.readonly`.
- **Instagram account of All Saints only**, to publish the channel's own Reels.

## What it does not do
- It does not collect, store, sell or share personal data about viewers or any other users.
- It does not access any Google or Instagram account other than the All Saints channel's own.
- It does not use cookies, analytics or tracking on viewers.

## Storage
OAuth credentials are stored as encrypted secrets in the project's GitHub repository settings and are used only to post the channel's own videos. Episode data (scripts, sources, publishing status) contains no personal data.

## Retention and deletion
- **Access tokens** are refreshed on each run and not stored. The **refresh token** is kept only as an encrypted GitHub secret until access is revoked; revoking access (links below) makes it unusable immediately, and the owner then deletes the secret.
- **YouTube API data** read by the tool (the channel's own name, handle and subscriber count) is used only during the run to confirm the right channel is connected and is not stored.
- **Uploaded video IDs and URLs** of the channel's own videos are kept in the project's episode records so the same video is not posted twice. Deleting a video on YouTube removes it; its record can be deleted on request.
- To request deletion of any data, use the contact below; requests are handled within 7 days.

## The website (allholysaints.com)
- **No cookies and no tracking.** The site sets no cookies. Visits are counted with Cloudflare Web Analytics, which is cookieless and reports only totals (pages, countries, devices), never individual visitors.
- **Hosting.** The site is served by Cloudflare, which processes IP addresses briefly to deliver pages and block attacks, under the [Cloudflare Privacy Policy](https://www.cloudflare.com/privacypolicy/).
- **Videos** load from YouTube (youtube-nocookie.com) only when you tap play; from then on YouTube's terms and Google's privacy policy apply.
- **Email digest** (when offered): if you subscribe, your email address is kept by our newsletter provider only to send the weekly email; every email has an unsubscribe link.
- **Support and links.** "Light a candle" opens our Ko-fi page; Ko-fi handles any payment under its own privacy policy, and we never see card details.

## Google and YouTube
This tool uses YouTube API Services. By watching All Saints videos on YouTube you are subject to the [YouTube Terms of Service](https://www.youtube.com/t/terms) and the [Google Privacy Policy](https://policies.google.com/privacy).
You can revoke the tool's access to a Google account at any time at [myaccount.google.com/permissions](https://myaccount.google.com/permissions) or via the [Google security settings page](https://security.google.com/settings/security/permissions).

## Contact
Questions or requests: email [hello@allholysaints.com](mailto:hello@allholysaints.com). You can also message [@all.holy.saints](https://www.instagram.com/all.holy.saints/) on Instagram.
