"""kklive.jp から実店舗URLを抽出するスクリプト"""
import httpx, re

headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'}
all_venue_urls = set()

SKIP = ['twitter.com', 'x.com', 'instagram.com', 'facebook.com', 'youtube.com',
        'apple.com', 'google', 'kkpoker', 'dl.kkpoker', 'kakaopage', 'line.me',
        'wp-content', 'wp-includes', 'feeds/', 'feed/', 'rss', 'amp/']

for page in range(1, 8):
    url = 'https://kklive.jp/pokerroom/' if page == 1 else f'https://kklive.jp/pokerroom/page/{page}/'
    try:
        r = httpx.get(url, follow_redirects=True, timeout=15, headers=headers)
        if r.status_code != 200:
            break
        links = re.findall(r'href=["\' ](https?://(?!kklive\.jp)[^"\'?\#\s]+)["\' >]', r.text)
        for l in links:
            if any(x in l for x in SKIP):
                continue
            all_venue_urls.add(l)
        print(f'Page {page}: {r.status_code}, venue URLs so far: {len(all_venue_urls)}')
    except Exception as e:
        print(f'Page {page} error: {e}')
        break

print()
print('=== Found venue URLs ===')
for u in sorted(all_venue_urls):
    print(u)
