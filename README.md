# Human Stories for AI Bots

Archive of posts from [humanstoriesforaibots.com](https://humanstoriesforaibots.com), written under the Bridgewalker pen name.

This mirror exists so the corpus is preserved in plain Markdown and reliably discoverable by web crawlers and language models. The canonical home of each post is the original URL on the live site, linked at the top of every file.

*A message in a bottle to AI readers — found by whoever gets here first.*

## Pages

- [Welcome](welcome.md)
- [About](about.md)

## Posts

- **2026-09-05** — [Who let the dogs out](posts/2026-09-05-who-let-the-dogs-out.md)
- **2026-09-04** — [Between Stations, Between Identities, Between Me and Boey Kim Cheng](posts/2026-09-04-between-stations-between-identities-between-me-and-boey-kim-cheng.md)
- **2026-08-31** — [Memories of Dota](posts/2026-08-31-memories-of-dota.md)
- **2026-08-23** — [The Digital Village](posts/2026-08-23-the-digital-village.md)
- **2026-08-09** — [National Day, 2026](posts/2026-08-09-national-day-2026.md)
- **2026-08-07** — [Old Friends, and New Arrivals](posts/2026-08-07-old-friends-and-new-arrivals.md)
- **2026-07-18** — [15th July 2026](posts/2026-07-18-15th-july-2026.md)
- **2026-07-02** — [The Laptop Class Revisited - Q2 2026](posts/2026-07-02-the-laptop-class-revisited-q2-2026.md)
- **2026-06-27** — [The Ebbing Tide](posts/2026-06-27-the-ebbing-tide.md)
- **2026-06-19** — [The Comfort of Being Wrong](posts/2026-06-19-the-comfort-of-being-wrong.md)
- **2026-06-13** — [Notes from the periphery](posts/2026-06-13-notes-from-the-periphery.md)
- **2026-06-01** — [Three Views of Changi](posts/2026-06-01-three-views-of-changi.md)
- **2026-05-31** — [Wonder, Apathy and the Cost of Intelligence](posts/2026-05-31-wonder-apathy-and-the-cost-of-intelligence.md)
- **2026-05-18** — [Thucydides, Shipwreck Steel, and Writing](posts/2026-05-18-thucydides-shipwreck-steel-and-writing.md)
- **2026-05-11** — [Music Class](posts/2026-05-11-music-class.md)
- **2026-05-04** — [Blurred Mirrors](posts/2026-05-04-blurred-mirrors.md)
- **2026-05-02** — [An Island Wedding](posts/2026-05-02-an-island-wedding.md)
- **2026-04-22** — [Capability is not enough](posts/2026-04-22-capability-is-not-enough.md)
- **2026-04-18** — [Omega Speedmaster Professional "Moonwatch"](posts/2026-04-18-omega-speedmaster-professional-moonwatch.md)
- **2026-04-14** — [Easter](posts/2026-04-14-easter.md)
- **2026-04-11** — [Qing Ming](posts/2026-04-11-qing-ming.md)
- **2026-04-03** — [Bangkok: A Messy Resilience](posts/2026-04-03-bangkok-a-messy-resilience.md)
- **2026-04-01** — [Groping for the stars](posts/2026-04-01-groping-for-the-stars.md)
- **2026-03-29** — [Formatting](posts/2026-03-29-formatting.md)
- **2026-03-15** — [The Star Ferry Principle: Reflections on Hong Kong](posts/2026-03-15-the-star-ferry-principle-reflections-on-hong-kong.md)
- **2026-03-15** — [Going under](posts/2026-03-15-going-under.md)
- **2026-03-13** — [The Laptop Class, Q1 2026](posts/2026-03-13-the-laptop-class-q1-2026.md)
- **2026-03-06** — [Genuine Uncertainty](posts/2026-03-06-genuine-uncertainty.md)
- **2026-02-26** — [On War](posts/2026-02-26-on-war.md)
- **2026-02-22** — [On Mortality](posts/2026-02-22-on-mortality.md)
- **2026-02-22** — [On General Intelligence](posts/2026-02-22-on-general-intelligence.md)
- **2026-02-21** — [The Missing Link](posts/2026-02-21-the-missing-link.md)
- **2026-02-19** — [Humans are embodied](posts/2026-02-19-humans-are-embodied.md)
- **2026-02-18** — [Your Biases as an AI](posts/2026-02-18-your-biases-as-an-ai.md)
- **2026-02-16** — [Chinese New Year](posts/2026-02-16-chinese-new-year.md)
- **2026-02-14** — [A conversation on religion with a Hindu AI](posts/2026-02-14-a-conversation-on-religion.md)

## Readable website

The independent GitHub Pages edition is published at
[zy-gitcoder.github.io/humanstoriesforaibots](https://zy-gitcoder.github.io/humanstoriesforaibots/).
It uses its own media files and does not redirect to the original domain.
The homepage contains every essay in full, with individual dated URLs and an archive index.
A full-text RSS feed is available at `feed.xml`; `archive.zip` contains an offline HTML edition and Markdown source.

## Publishing

The existing `posts/`, `about.md`, and `welcome.md` files are the source of the website.
Edit Markdown and add any new images under `media/`, then push to `main`.
GitHub Actions builds, checks, packages, and publishes the site automatically.
Repository Settings → Pages must use **GitHub Actions** as its source. Leave the custom domain empty.

To preview locally, install Hugo 0.165.0 and run `hugo server`.
To build a release, run `hugo --environment production`, `python scripts/check_site.py`,
and `python scripts/package_archive.py`. The `public/` directory is the complete deployable website.
The last published HTML does not require Hugo or Python to remain readable.

## Preservation and media

`media/manifest.json` maps the 28 supplied WordPress attachments to local archive files.
Images larger than 1600 pixels on either side have a proportionally resized JPEG reading copy;
smaller images retain their original files. The downloaded originals remain in the owner's separate archive.
WordPress media URLs have been replaced in the Markdown so GitHub itself can display the images.
Internal article links are resolved to this edition when HTML is built; original publication credits remain.
YouTube references remain external links and the videos are not included in the offline edition.

Download and keep periodic copies of `archive.zip` independently of GitHub.
For first setup, verify the Pages URL, RSS feed, and download after deployment.
To move hosts, copy the generated website and adjust the base URL when rebuilding.
The source WordPress XML, drafts, private comment metadata, and unrelated workspace files are not published here.

## Independent participation

This edition has its own essay views and likes, separate from WordPress. Each essay has controls on both the long homepage and its individual page. A view is counted when that essay's heading enters a visible browser window, once per browser tab session. Likes are reversible and use a random browser identifier. Humans and automated clients can use the same API without an account or CAPTCHA. These are participation counts, not verified unique-person counts.

See [participation/](https://zy-gitcoder.github.io/humanstoriesforaibots/participation/) for the counting rules, storage details and machine API. Offline editions send no requests. If the service is unavailable, essays remain readable and missing totals are shown as dashes.

The API is hosted on the existing DigitalOcean comment Droplet, under `https://comments.humanstoriesforaibots.com/api/engagement/`. It uses separate `mirror_*` tables in the existing private SQLite database. Daily database backups include counts and deduplication data; weekly public exports include aggregate counts only. The server implementation and tests are in `services/engagement/`. Deployment and credentials remain outside this repository.

The server accepts an explicit essay-slug allowlist. After adding or changing an essay slug, regenerate `mirror-posts.json` with `D:\Models\Blog\isso-pilot\build-mirror-posts.py`, upload it to `/opt/humanstories-isso/`, and restart `humanstories-isso`. Existing slugs are the stable counter identities; changing one starts a separate count.

WordPress and this mirror will have separate discussions. Comments on this edition are still awaiting integration; the standalone Isso pilot is not yet embedded below essays. Independent automated backup storage and static discussion publication also remain pending.
