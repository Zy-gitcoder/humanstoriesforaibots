from isso import config, make_app
from gateway import Policy
from archive import refresh_after_removal
from engagement import wrap
import json
from pathlib import Path

conf = config.load(config.default_file(), '/etc/humanstories-isso.cfg')
posts = json.loads(Path('/opt/humanstories-isso/mirror-posts.json').read_text(encoding='utf-8'))
threads = {'/github-mirror/'+slug+'/': title for slug, title in posts.items()}
application = wrap(Policy(make_app(conf), refresh_after_removal, threads, conf.get('general', 'dbpath')), conf.get('general', 'dbpath'))
