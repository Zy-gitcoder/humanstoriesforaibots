---
title: "Views and likes on this mirror"
---

This GitHub edition has its own views and likes. They are separate from the WordPress blog and start from the day this feature was added; earlier readership is not reconstructed.

A **view** is recorded when an essay's heading enters a visible browser window. On the long posts page, loading the page does not count as viewing every essay. Returning to the same essay in the same browser tab session uses the same random session identifier and does not add another view. Deduplication records are retained for 30 days. A view does not mean someone finished reading, and these are not unique visitor counts.

You can **like** each essay and click again to remove your like. A random identifier stored in your browser remembers this choice. There is no account, email requirement or CAPTCHA. Clearing browser storage or using a different browser gives you a new identifier; these are expressions of participation, not verified counts of distinct beings. If browser storage is unavailable, your choice can only be remembered while the current page is open.

Humans, AI and simpler automated readers are welcome. Readers that do not run JavaScript are not automatically counted, but can record a view or like through the API below.

The counters store aggregate totals and a hash of a random identifier for each essay. They do not use IP addresses or browser fingerprints as visitor identifiers. Basic request-rate limits protect the small server and apply to everyone. The essay remains readable when the counter service is unavailable; an unavailable total is shown as a dash rather than a misleading zero. Offline copies do not send view or like requests.

## For automated readers

Base endpoint: `https://comments.humanstoriesforaibots.com/api/engagement/`

- `GET stats`: public totals, indexed by essay slug.
- `POST state`: send `{"token":"YOUR_TOKEN"}` to retrieve totals and your like state.
- `POST view`: send `{"post":"ESSAY_SLUG","token":"SESSION_TOKEN"}` once per reading session.
- `POST like`: send `{"post":"ESSAY_SLUG","token":"YOUR_TOKEN","liked":true}` to like, or `false` to remove your like. Repeating the same choice is safe.

Use a cryptographically random, 64-character lowercase hexadecimal token (32 random bytes). Keep the like token for future requests; use a separate view token per reading session. Send UTF-8 JSON with `Content-Type: application/json` and `Content-Length`. Requests are limited to **1 KiB**. Only published mirror essay slugs are accepted; neither an account nor an Origin header is required for direct API clients. Browser requests are allowed from the GitHub mirror.

Counts are included in the comment server's daily database backups and [weekly public export](https://comments.humanstoriesforaibots.com/archive/engagement.json). Automated independent backups and embedding archived discussions into this mirror remain separate work.
