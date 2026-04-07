"""RSS feed URL constants — DEPRECATED: seed data only.

Feed constants below are retained only as seed data for migration 012.
Crawlers now read from the feed_source database table.
The FeedSource TypedDict is still used as an interface type by crawler code.
"""

from __future__ import annotations

from typing import TypedDict


class FeedSource(TypedDict):
    url: str
    name: str
    category: str
    locale: str


# ---------------------------------------------------------------------------
# Domestic Korean News (120+)
# ---------------------------------------------------------------------------

KR_NEWS_FEEDS: list[FeedSource] = [
    # --- 종합 ---
    {
        "url": "https://www.chosun.com/arc/outboundfeeds/rss/?outputType=xml",
        "name": "조선일보",
        "category": "general",
        "locale": "ko",
    },
    {
        "url": "https://www.donga.com/news/rss/total.xml",
        "name": "동아일보",
        "category": "general",
        "locale": "ko",
    },
    {
        "url": "https://www.joongang.co.kr/rss/all",
        "name": "중앙일보",
        "category": "general",
        "locale": "ko",
    },
    {"url": "https://www.hani.co.kr/rss/", "name": "한겨레", "category": "general", "locale": "ko"},
    {
        "url": "https://www.khan.co.kr/rss/rssdata/total_news.xml",
        "name": "경향신문",
        "category": "general",
        "locale": "ko",
    },
    {
        "url": "https://www.kmib.co.kr/rss/all.xml",
        "name": "국민일보",
        "category": "general",
        "locale": "ko",
    },
    {
        "url": "https://www.segye.com/rss/segye_total.xml",
        "name": "세계일보",
        "category": "general",
        "locale": "ko",
    },
    {
        "url": "https://www.munhwa.com/rss/munhwa_total.xml",
        "name": "문화일보",
        "category": "general",
        "locale": "ko",
    },
    {
        "url": "https://www.seoul.co.kr/xml/rss/rss_seoulnews.xml",
        "name": "서울신문",
        "category": "general",
        "locale": "ko",
    },
    {
        "url": "https://news.heraldcorp.com/common/rss_xml.php?ct=010000000000",
        "name": "헤럴드경제",
        "category": "general",
        "locale": "ko",
    },
    # --- 정치 ---
    {
        "url": "https://www.chosun.com/arc/outboundfeeds/rss/category/politics/?outputType=xml",
        "name": "조선일보 정치",
        "category": "politics",
        "locale": "ko",
    },
    {
        "url": "https://www.donga.com/news/rss/politics.xml",
        "name": "동아일보 정치",
        "category": "politics",
        "locale": "ko",
    },
    {
        "url": "https://www.hani.co.kr/rss/politics/",
        "name": "한겨레 정치",
        "category": "politics",
        "locale": "ko",
    },
    {
        "url": "https://www.khan.co.kr/rss/rssdata/politic_news.xml",
        "name": "경향신문 정치",
        "category": "politics",
        "locale": "ko",
    },
    {
        "url": "https://www.ohmynews.com/rss/politics.xml",
        "name": "오마이뉴스 정치",
        "category": "politics",
        "locale": "ko",
    },
    {
        "url": "https://newsis.com/rss/politics.xml",
        "name": "뉴시스 정치",
        "category": "politics",
        "locale": "ko",
    },
    {
        "url": "https://www.yonhapnews.co.kr/RSS/politics.xml",
        "name": "연합뉴스 정치",
        "category": "politics",
        "locale": "ko",
    },
    {
        "url": "https://www.nocutnews.co.kr/rss/politics.xml",
        "name": "노컷뉴스 정치",
        "category": "politics",
        "locale": "ko",
    },
    {
        "url": "https://www.pressian.com/rss/politics.xml",
        "name": "프레시안 정치",
        "category": "politics",
        "locale": "ko",
    },
    {
        "url": "https://www.mediatoday.co.kr/rss/politics.xml",
        "name": "미디어오늘 정치",
        "category": "politics",
        "locale": "ko",
    },
    # --- 경제 ---
    {
        "url": "https://www.mk.co.kr/rss/30000001/",
        "name": "매일경제",
        "category": "economy",
        "locale": "ko",
    },
    {
        "url": "https://www.hankyung.com/feed/all-news",
        "name": "한국경제",
        "category": "economy",
        "locale": "ko",
    },
    {
        "url": "https://www.sedaily.com/RSS/CM01",
        "name": "서울경제",
        "category": "economy",
        "locale": "ko",
    },
    {
        "url": "https://www.fnnews.com/rss/fn_total_news.xml",
        "name": "파이낸셜뉴스",
        "category": "economy",
        "locale": "ko",
    },
    {
        "url": "https://www.asiae.co.kr/rss/all.xml",
        "name": "아시아경제",
        "category": "economy",
        "locale": "ko",
    },
    {
        "url": "https://www.edaily.co.kr/rss/all.xml",
        "name": "이데일리",
        "category": "economy",
        "locale": "ko",
    },
    {
        "url": "https://www.mt.co.kr/rss/all.xml",
        "name": "머니투데이",
        "category": "economy",
        "locale": "ko",
    },
    {
        "url": "https://www.etoday.co.kr/rss/all.xml",
        "name": "이투데이",
        "category": "economy",
        "locale": "ko",
    },
    {
        "url": "https://www.inews24.com/rss/economy.xml",
        "name": "아이뉴스24 경제",
        "category": "economy",
        "locale": "ko",
    },
    {
        "url": "https://biz.chosun.com/rss/all.xml",
        "name": "조선비즈",
        "category": "economy",
        "locale": "ko",
    },
    {
        "url": "https://www.bloter.net/feed",
        "name": "블로터 경제",
        "category": "economy",
        "locale": "ko",
    },
    {
        "url": "https://www.thebellkorea.com/rss/all.xml",
        "name": "더벨",
        "category": "economy",
        "locale": "ko",
    },
    {
        "url": "https://www.thebell.co.kr/rss/all.xml",
        "name": "더벨(증권)",
        "category": "economy",
        "locale": "ko",
    },
    {
        "url": "https://www.sisajournal-e.com/rss/all.xml",
        "name": "시사저널e",
        "category": "economy",
        "locale": "ko",
    },
    {
        "url": "https://www.newspim.com/rss/all.xml",
        "name": "뉴스핌",
        "category": "economy",
        "locale": "ko",
    },
    # --- IT/과학 ---
    {
        "url": "https://www.zdnet.co.kr/rss/all.xml",
        "name": "ZDNet Korea",
        "category": "it",
        "locale": "ko",
    },
    {
        "url": "https://www.etnews.com/rss/all.xml",
        "name": "전자신문",
        "category": "it",
        "locale": "ko",
    },
    {
        "url": "https://www.inews24.com/rss/it.xml",
        "name": "아이뉴스24 IT",
        "category": "it",
        "locale": "ko",
    },
    {
        "url": "https://www.dt.co.kr/rss/all.xml",
        "name": "디지털타임스",
        "category": "it",
        "locale": "ko",
    },
    {"url": "https://www.bloter.net/feed", "name": "블로터", "category": "it", "locale": "ko"},
    {
        "url": "https://www.itworld.co.kr/rss/feed.xml",
        "name": "ITWorld Korea",
        "category": "it",
        "locale": "ko",
    },
    {
        "url": "https://www.boannews.com/rss/news.xml",
        "name": "보안뉴스",
        "category": "it",
        "locale": "ko",
    },
    {
        "url": "https://byline.network/feed/",
        "name": "바이라인네트워크",
        "category": "it",
        "locale": "ko",
    },
    {
        "url": "https://www.aitimes.com/rss/all.xml",
        "name": "AI타임스",
        "category": "it",
        "locale": "ko",
    },
    {
        "url": "https://www.irobotnews.com/rss/all.xml",
        "name": "로봇신문",
        "category": "it",
        "locale": "ko",
    },
    {
        "url": "https://www.sciencetimes.co.kr/feed/",
        "name": "사이언스타임즈",
        "category": "it",
        "locale": "ko",
    },
    {
        "url": "https://www.dongascience.com/rss/all.xml",
        "name": "동아사이언스",
        "category": "it",
        "locale": "ko",
    },
    {
        "url": "https://www.hellodd.com/rss/all.xml",
        "name": "헬로디디",
        "category": "it",
        "locale": "ko",
    },
    {"url": "https://platum.kr/feed", "name": "플래텀", "category": "it", "locale": "ko"},
    {
        "url": "https://www.venturesquare.net/feed",
        "name": "벤처스퀘어",
        "category": "it",
        "locale": "ko",
    },
    # --- 연예 ---
    {
        "url": "https://www.sportsseoul.com/rss/entertainment.xml",
        "name": "스포츠서울 연예",
        "category": "entertainment",
        "locale": "ko",
    },
    {
        "url": "https://entertain.naver.com/rss/all.xml",
        "name": "네이버 연예",
        "category": "entertainment",
        "locale": "ko",
    },
    {
        "url": "https://www.xportsnews.com/rss/all.xml",
        "name": "엑스포츠뉴스",
        "category": "entertainment",
        "locale": "ko",
    },
    {
        "url": "https://www.tvreport.co.kr/rss/all.xml",
        "name": "TV리포트",
        "category": "entertainment",
        "locale": "ko",
    },
    {
        "url": "https://www.stardailynews.co.kr/rss/all.xml",
        "name": "스타데일리뉴스",
        "category": "entertainment",
        "locale": "ko",
    },
    {
        "url": "https://www.topstarnews.net/rss/all.xml",
        "name": "톱스타뉴스",
        "category": "entertainment",
        "locale": "ko",
    },
    {
        "url": "https://www.osen.co.kr/rss/total.xml",
        "name": "OSEN",
        "category": "entertainment",
        "locale": "ko",
    },
    {
        "url": "https://www.newsen.com/rss/all.xml",
        "name": "뉴센",
        "category": "entertainment",
        "locale": "ko",
    },
    {
        "url": "https://www.dispatch.co.kr/rss/all.xml",
        "name": "디스패치",
        "category": "entertainment",
        "locale": "ko",
    },
    {
        "url": "https://tenasia.hankyung.com/rss/all.xml",
        "name": "텐아시아",
        "category": "entertainment",
        "locale": "ko",
    },
    # --- 스포츠 ---
    {
        "url": "https://sports.news.naver.com/rss/all.xml",
        "name": "네이버 스포츠",
        "category": "sports",
        "locale": "ko",
    },
    {
        "url": "https://www.sportsseoul.com/rss/sports.xml",
        "name": "스포츠서울",
        "category": "sports",
        "locale": "ko",
    },
    {
        "url": "https://www.sportalkorea.com/rss/all.xml",
        "name": "스포탈코리아",
        "category": "sports",
        "locale": "ko",
    },
    {
        "url": "https://www.mydaily.co.kr/rss/sports.xml",
        "name": "마이데일리 스포츠",
        "category": "sports",
        "locale": "ko",
    },
    {
        "url": "https://www.osen.co.kr/rss/sports.xml",
        "name": "OSEN 스포츠",
        "category": "sports",
        "locale": "ko",
    },
    {
        "url": "https://sports.donga.com/rss/all.xml",
        "name": "동아스포츠",
        "category": "sports",
        "locale": "ko",
    },
    {
        "url": "https://sports.chosun.com/rss/all.xml",
        "name": "스포츠조선",
        "category": "sports",
        "locale": "ko",
    },
    {
        "url": "https://isplus.com/rss/all.xml",
        "name": "일간스포츠",
        "category": "sports",
        "locale": "ko",
    },
    {
        "url": "https://www.sportsw.kr/rss/all.xml",
        "name": "스포츠W",
        "category": "sports",
        "locale": "ko",
    },
    {
        "url": "https://www.goal.com/kr/feeds/news",
        "name": "골닷컴 코리아",
        "category": "sports",
        "locale": "ko",
    },
    # --- 사회 ---
    {
        "url": "https://www.yonhapnews.co.kr/RSS/society.xml",
        "name": "연합뉴스 사회",
        "category": "general",
        "locale": "ko",
    },
    {
        "url": "https://www.donga.com/news/rss/society.xml",
        "name": "동아일보 사회",
        "category": "general",
        "locale": "ko",
    },
    {
        "url": "https://www.hani.co.kr/rss/society/",
        "name": "한겨레 사회",
        "category": "general",
        "locale": "ko",
    },
    {
        "url": "https://newsis.com/rss/society.xml",
        "name": "뉴시스 사회",
        "category": "general",
        "locale": "ko",
    },
    {
        "url": "https://www.news1.kr/rss/society.xml",
        "name": "뉴스1 사회",
        "category": "general",
        "locale": "ko",
    },
    # --- 포탈/통신 ---
    {
        "url": "https://www.yonhapnews.co.kr/RSS/headline.xml",
        "name": "연합뉴스 헤드라인",
        "category": "general",
        "locale": "ko",
    },
    {
        "url": "https://news.sbs.co.kr/news/SectionRssFeed.do?sectionId=01",
        "name": "SBS 뉴스",
        "category": "general",
        "locale": "ko",
    },
    {
        "url": "https://imnews.imbc.com/rss/all.xml",
        "name": "MBC 뉴스",
        "category": "general",
        "locale": "ko",
    },
    {
        "url": "https://news.kbs.co.kr/local/news/rss/rss.xml",
        "name": "KBS 뉴스",
        "category": "general",
        "locale": "ko",
    },
    {
        "url": "https://www.yna.co.kr/RSS/news.xml",
        "name": "연합뉴스TV",
        "category": "general",
        "locale": "ko",
    },
    {
        "url": "https://www.newsis.com/rss/all.xml",
        "name": "뉴시스",
        "category": "general",
        "locale": "ko",
    },
    {
        "url": "https://www.news1.kr/rss/all.xml",
        "name": "뉴스1",
        "category": "general",
        "locale": "ko",
    },
    # --- 지역 ---
    {
        "url": "https://www.busan.com/rss/all.xml",
        "name": "부산일보",
        "category": "general",
        "locale": "ko",
    },
    {
        "url": "https://www.imaeil.com/rss/all.xml",
        "name": "매일신문",
        "category": "general",
        "locale": "ko",
    },
    {
        "url": "https://www.kwangju.co.kr/rss/all.xml",
        "name": "광주일보",
        "category": "general",
        "locale": "ko",
    },
    {
        "url": "https://www.kwnews.co.kr/rss/all.xml",
        "name": "강원일보",
        "category": "general",
        "locale": "ko",
    },
    {
        "url": "https://www.jnilbo.com/rss/all.xml",
        "name": "전남일보",
        "category": "general",
        "locale": "ko",
    },
    {
        "url": "https://www.daejonilbo.com/rss/all.xml",
        "name": "대전일보",
        "category": "general",
        "locale": "ko",
    },
    {
        "url": "https://www.jejunews.com/rss/all.xml",
        "name": "제주일보",
        "category": "general",
        "locale": "ko",
    },
    # --- 시사/매거진 ---
    {
        "url": "https://www.sisajournal.com/rss/all.xml",
        "name": "시사저널",
        "category": "general",
        "locale": "ko",
    },
    {
        "url": "https://www.sisain.co.kr/rss/all.xml",
        "name": "시사IN",
        "category": "general",
        "locale": "ko",
    },
    {
        "url": "https://www.hankookilbo.com/rss/all.xml",
        "name": "한국일보",
        "category": "general",
        "locale": "ko",
    },
    {
        "url": "https://www.newstof.com/rss/all.xml",
        "name": "뉴스토프",
        "category": "general",
        "locale": "ko",
    },
    # --- 생활/문화 ---
    {
        "url": "https://www.donga.com/news/rss/culture.xml",
        "name": "동아일보 문화",
        "category": "entertainment",
        "locale": "ko",
    },
    {
        "url": "https://www.hani.co.kr/rss/culture/",
        "name": "한겨레 문화",
        "category": "entertainment",
        "locale": "ko",
    },
    {
        "url": "https://www.mk.co.kr/rss/30800011/",
        "name": "매경 문화",
        "category": "entertainment",
        "locale": "ko",
    },
    # --- 건강/의료 ---
    {
        "url": "https://www.healthinnews.co.kr/rss/all.xml",
        "name": "헬스인뉴스",
        "category": "general",
        "locale": "ko",
    },
    {
        "url": "https://www.medicaltimes.com/rss/all.xml",
        "name": "메디컬타임즈",
        "category": "general",
        "locale": "ko",
    },
    {
        "url": "https://www.rapportian.com/rss/all.xml",
        "name": "라포르시안",
        "category": "general",
        "locale": "ko",
    },
    # --- 부동산 ---
    {
        "url": "https://www.mk.co.kr/rss/50300009/",
        "name": "매경 부동산",
        "category": "economy",
        "locale": "ko",
    },
    {
        "url": "https://www.asiae.co.kr/rss/realestate.xml",
        "name": "아시아경제 부동산",
        "category": "economy",
        "locale": "ko",
    },
    # --- 자동차 ---
    {
        "url": "https://www.autoherald.co.kr/rss/all.xml",
        "name": "오토헤럴드",
        "category": "general",
        "locale": "ko",
    },
    {
        "url": "https://www.autodaily.co.kr/rss/all.xml",
        "name": "오토데일리",
        "category": "general",
        "locale": "ko",
    },
    # --- 교육 ---
    {
        "url": "https://www.veritas-a.com/rss/all.xml",
        "name": "베리타스알파",
        "category": "general",
        "locale": "ko",
    },
    {
        "url": "https://www.edujin.co.kr/rss/all.xml",
        "name": "에듀진",
        "category": "general",
        "locale": "ko",
    },
    # --- 국방/외교 ---
    {
        "url": "https://www.demaclub.com/rss/all.xml",
        "name": "국방일보",
        "category": "politics",
        "locale": "ko",
    },
    # --- 환경 ---
    {
        "url": "https://www.greenpostkorea.co.kr/rss/all.xml",
        "name": "그린포스트코리아",
        "category": "general",
        "locale": "ko",
    },
    # --- 농업 ---
    {
        "url": "https://www.agrinet.co.kr/rss/all.xml",
        "name": "한국농어민신문",
        "category": "general",
        "locale": "ko",
    },
    # --- 법률 ---
    {
        "url": "https://www.lawtimes.co.kr/rss/all.xml",
        "name": "법률신문",
        "category": "general",
        "locale": "ko",
    },
    # --- 스타트업 ---
    {
        "url": "https://www.startupn.kr/rss/all.xml",
        "name": "스타트업엔",
        "category": "economy",
        "locale": "ko",
    },
    {
        "url": "https://www.besuccess.com/feed/",
        "name": "비석세스",
        "category": "economy",
        "locale": "ko",
    },
]


# ---------------------------------------------------------------------------
# Global News (70+)
# ---------------------------------------------------------------------------

GLOBAL_NEWS_FEEDS: list[FeedSource] = [
    # --- General / Wire Services ---
    {
        "url": "https://feeds.reuters.com/reuters/topNews",
        "name": "Reuters Top",
        "category": "general",
        "locale": "en",
    },
    {
        "url": "https://feeds.reuters.com/reuters/worldNews",
        "name": "Reuters World",
        "category": "general",
        "locale": "en",
    },
    {
        "url": "https://feeds.bbci.co.uk/news/rss.xml",
        "name": "BBC News",
        "category": "general",
        "locale": "en",
    },
    {
        "url": "https://feeds.bbci.co.uk/news/world/rss.xml",
        "name": "BBC World",
        "category": "general",
        "locale": "en",
    },
    {
        "url": "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml",
        "name": "NYT Home",
        "category": "general",
        "locale": "en",
    },
    {
        "url": "https://rss.nytimes.com/services/xml/rss/nyt/World.xml",
        "name": "NYT World",
        "category": "general",
        "locale": "en",
    },
    {
        "url": "https://feeds.washingtonpost.com/rss/world",
        "name": "Washington Post World",
        "category": "general",
        "locale": "en",
    },
    {
        "url": "https://www.theguardian.com/world/rss",
        "name": "The Guardian World",
        "category": "general",
        "locale": "en",
    },
    {
        "url": "https://rss.cnn.com/rss/edition.rss",
        "name": "CNN International",
        "category": "general",
        "locale": "en",
    },
    {
        "url": "https://abcnews.go.com/abcnews/topstories",
        "name": "ABC News Top",
        "category": "general",
        "locale": "en",
    },
    {
        "url": "https://feeds.nbcnews.com/nbcnews/public/news",
        "name": "NBC News",
        "category": "general",
        "locale": "en",
    },
    {
        "url": "https://www.aljazeera.com/xml/rss/all.xml",
        "name": "Al Jazeera",
        "category": "general",
        "locale": "en",
    },
    {
        "url": "https://www.france24.com/en/rss",
        "name": "France 24",
        "category": "general",
        "locale": "en",
    },
    {
        "url": "https://www3.nhk.or.jp/rss/news/cat0.xml",
        "name": "NHK World",
        "category": "general",
        "locale": "en",
    },
    {
        "url": "https://www.dw.com/rss/en/top-stories",
        "name": "DW News",
        "category": "general",
        "locale": "en",
    },
    # --- Politics ---
    {
        "url": "https://rss.nytimes.com/services/xml/rss/nyt/Politics.xml",
        "name": "NYT Politics",
        "category": "politics",
        "locale": "en",
    },
    {
        "url": "https://feeds.reuters.com/reuters/politicsNews",
        "name": "Reuters Politics",
        "category": "politics",
        "locale": "en",
    },
    {
        "url": "https://rss.politico.com/politics-news.xml",
        "name": "Politico",
        "category": "politics",
        "locale": "en",
    },
    {
        "url": "https://thehill.com/rss/syndicator/19110",
        "name": "The Hill",
        "category": "politics",
        "locale": "en",
    },
    {
        "url": "https://www.axios.com/feeds/feed.rss",
        "name": "Axios",
        "category": "politics",
        "locale": "en",
    },
    # --- Economy / Business ---
    {
        "url": "https://feeds.reuters.com/reuters/businessNews",
        "name": "Reuters Business",
        "category": "economy",
        "locale": "en",
    },
    {
        "url": "https://rss.nytimes.com/services/xml/rss/nyt/Business.xml",
        "name": "NYT Business",
        "category": "economy",
        "locale": "en",
    },
    {
        "url": "https://feeds.bloomberg.com/markets/news.rss",
        "name": "Bloomberg Markets",
        "category": "economy",
        "locale": "en",
    },
    {
        "url": "https://www.ft.com/?format=rss",
        "name": "Financial Times",
        "category": "economy",
        "locale": "en",
    },
    {
        "url": "https://www.economist.com/rss",
        "name": "The Economist",
        "category": "economy",
        "locale": "en",
    },
    {
        "url": "https://www.cnbc.com/id/100003114/device/rss/rss.html",
        "name": "CNBC",
        "category": "economy",
        "locale": "en",
    },
    {
        "url": "https://www.marketwatch.com/rss/topstories",
        "name": "MarketWatch",
        "category": "economy",
        "locale": "en",
    },
    {"url": "https://fortune.com/feed/", "name": "Fortune", "category": "economy", "locale": "en"},
    {
        "url": "https://www.forbes.com/innovation/feed/",
        "name": "Forbes Innovation",
        "category": "economy",
        "locale": "en",
    },
    {
        "url": "https://hbr.org/rss",
        "name": "Harvard Business Review",
        "category": "economy",
        "locale": "en",
    },
    # --- IT / Tech ---
    {"url": "https://techcrunch.com/feed/", "name": "TechCrunch", "category": "it", "locale": "en"},
    {
        "url": "https://www.theverge.com/rss/index.xml",
        "name": "The Verge",
        "category": "it",
        "locale": "en",
    },
    {
        "url": "https://feeds.arstechnica.com/arstechnica/index",
        "name": "Ars Technica",
        "category": "it",
        "locale": "en",
    },
    {"url": "https://www.wired.com/feed/rss", "name": "Wired", "category": "it", "locale": "en"},
    {
        "url": "https://feeds.feedburner.com/TechCrunchIT",
        "name": "TechCrunch IT",
        "category": "it",
        "locale": "en",
    },
    {
        "url": "https://www.zdnet.com/news/rss.xml",
        "name": "ZDNet",
        "category": "it",
        "locale": "en",
    },
    {"url": "https://www.cnet.com/rss/news/", "name": "CNET", "category": "it", "locale": "en"},
    {
        "url": "https://www.engadget.com/rss.xml",
        "name": "Engadget",
        "category": "it",
        "locale": "en",
    },
    {
        "url": "https://www.technologyreview.com/feed/",
        "name": "MIT Tech Review",
        "category": "it",
        "locale": "en",
    },
    {
        "url": "https://venturebeat.com/feed/",
        "name": "VentureBeat",
        "category": "it",
        "locale": "en",
    },
    {"url": "https://9to5mac.com/feed/", "name": "9to5Mac", "category": "it", "locale": "en"},
    {"url": "https://9to5google.com/feed/", "name": "9to5Google", "category": "it", "locale": "en"},
    {
        "url": "https://www.androidcentral.com/rss.xml",
        "name": "Android Central",
        "category": "it",
        "locale": "en",
    },
    {"url": "https://hackernoon.com/feed", "name": "HackerNoon", "category": "it", "locale": "en"},
    {
        "url": "https://thenextweb.com/feed/",
        "name": "The Next Web",
        "category": "it",
        "locale": "en",
    },
    {
        "url": "https://www.tomshardware.com/feeds/all",
        "name": "Tom's Hardware",
        "category": "it",
        "locale": "en",
    },
    {
        "url": "https://www.infoworld.com/index.rss",
        "name": "InfoWorld",
        "category": "it",
        "locale": "en",
    },
    {
        "url": "https://www.theregister.com/headlines.atom",
        "name": "The Register",
        "category": "it",
        "locale": "en",
    },
    {
        "url": "https://www.computerworld.com/index.rss",
        "name": "Computerworld",
        "category": "it",
        "locale": "en",
    },
    # --- Science ---
    {
        "url": "https://rss.nytimes.com/services/xml/rss/nyt/Science.xml",
        "name": "NYT Science",
        "category": "it",
        "locale": "en",
    },
    {
        "url": "https://www.nature.com/nature.rss",
        "name": "Nature",
        "category": "it",
        "locale": "en",
    },
    {
        "url": "https://www.sciencedaily.com/rss/all.xml",
        "name": "Science Daily",
        "category": "it",
        "locale": "en",
    },
    {"url": "https://phys.org/rss-feed/", "name": "Phys.org", "category": "it", "locale": "en"},
    # --- Entertainment ---
    {
        "url": "https://www.hollywoodreporter.com/feed/",
        "name": "Hollywood Reporter",
        "category": "entertainment",
        "locale": "en",
    },
    {
        "url": "https://variety.com/feed/",
        "name": "Variety",
        "category": "entertainment",
        "locale": "en",
    },
    {
        "url": "https://deadline.com/feed/",
        "name": "Deadline",
        "category": "entertainment",
        "locale": "en",
    },
    {
        "url": "https://ew.com/feed/",
        "name": "Entertainment Weekly",
        "category": "entertainment",
        "locale": "en",
    },
    {
        "url": "https://www.rollingstone.com/feed/",
        "name": "Rolling Stone",
        "category": "entertainment",
        "locale": "en",
    },
    {
        "url": "https://pitchfork.com/rss/news/",
        "name": "Pitchfork",
        "category": "entertainment",
        "locale": "en",
    },
    # --- Sports ---
    {
        "url": "https://www.espn.com/espn/rss/news",
        "name": "ESPN",
        "category": "sports",
        "locale": "en",
    },
    {
        "url": "https://rss.nytimes.com/services/xml/rss/nyt/Sports.xml",
        "name": "NYT Sports",
        "category": "sports",
        "locale": "en",
    },
    {
        "url": "https://feeds.bbci.co.uk/sport/rss.xml",
        "name": "BBC Sport",
        "category": "sports",
        "locale": "en",
    },
    {
        "url": "https://www.skysports.com/rss/12040",
        "name": "Sky Sports",
        "category": "sports",
        "locale": "en",
    },
    {
        "url": "https://www.goal.com/feeds/news?fmt=rss",
        "name": "Goal.com",
        "category": "sports",
        "locale": "en",
    },
    # --- Asia-Pacific ---
    {
        "url": "https://www.scmp.com/rss/91/feed",
        "name": "South China Morning Post",
        "category": "general",
        "locale": "en",
    },
    {
        "url": "https://www.straitstimes.com/news/asia/rss.xml",
        "name": "Straits Times Asia",
        "category": "general",
        "locale": "en",
    },
    {
        "url": "https://japantoday.com/feed",
        "name": "Japan Today",
        "category": "general",
        "locale": "en",
    },
    {
        "url": "https://www.koreaherald.com/rss/all.xml",
        "name": "Korea Herald",
        "category": "general",
        "locale": "en",
    },
    {
        "url": "https://en.yna.co.kr/RSS/news.xml",
        "name": "Yonhap English",
        "category": "general",
        "locale": "en",
    },
    {
        "url": "https://koreajoongangdaily.joins.com/rss/all.xml",
        "name": "Korea JoongAng Daily",
        "category": "general",
        "locale": "en",
    },
]


# ---------------------------------------------------------------------------
# Google Trends (RSS, geo=KR)
# ---------------------------------------------------------------------------

GOOGLE_TRENDS_FEEDS: list[FeedSource] = [
    {
        "url": "https://trends.google.com/trending/rss?geo=KR",
        "name": "Google Trends KR",
        "category": "general",
        "locale": "ko",
    },
    {
        "url": "https://trends.google.com/trending/rss?geo=US",
        "name": "Google Trends US",
        "category": "general",
        "locale": "en",
    },
    {
        "url": "https://trends.google.com/trending/rss?geo=JP",
        "name": "Google Trends JP",
        "category": "general",
        "locale": "ja",
    },
]


# ---------------------------------------------------------------------------
# Community RSS (DC Inside, FM Korea)
# ---------------------------------------------------------------------------

COMMUNITY_FEEDS: list[FeedSource] = [
    # DC Inside major galleries (RSS)
    {
        "url": "https://rss.dcinside.com/?mi=hot",
        "name": "DC 핫갤",
        "category": "general",
        "locale": "ko",
    },
    {
        "url": "https://rss.dcinside.com/?mi=realtime_hot",
        "name": "DC 실시간 핫갤",
        "category": "general",
        "locale": "ko",
    },
    {
        "url": "https://rss.dcinside.com/?mi=baseball_new11",
        "name": "DC 야구갤",
        "category": "sports",
        "locale": "ko",
    },
    {
        "url": "https://rss.dcinside.com/?mi=stock",
        "name": "DC 주식갤",
        "category": "economy",
        "locale": "ko",
    },
    {
        "url": "https://rss.dcinside.com/?mi=car",
        "name": "DC 자동차갤",
        "category": "general",
        "locale": "ko",
    },
    {
        "url": "https://rss.dcinside.com/?mi=programming",
        "name": "DC 프로그래밍갤",
        "category": "it",
        "locale": "ko",
    },
    {"url": "https://rss.dcinside.com/?mi=ai", "name": "DC AI갤", "category": "it", "locale": "ko"},
    {
        "url": "https://rss.dcinside.com/?mi=game",
        "name": "DC 게임갤",
        "category": "entertainment",
        "locale": "ko",
    },
    {
        "url": "https://rss.dcinside.com/?mi=movie",
        "name": "DC 영화갤",
        "category": "entertainment",
        "locale": "ko",
    },
    {
        "url": "https://rss.dcinside.com/?mi=football_new6",
        "name": "DC 해외축구갤",
        "category": "sports",
        "locale": "ko",
    },
    # FM Korea
    {
        "url": "https://www.fmkorea.com/index.php?mid=hotdeal&act=rss",
        "name": "FM Korea 핫딜",
        "category": "general",
        "locale": "ko",
    },
    {
        "url": "https://www.fmkorea.com/index.php?mid=best&act=rss",
        "name": "FM Korea 베스트",
        "category": "general",
        "locale": "ko",
    },
    {
        "url": "https://www.fmkorea.com/index.php?mid=humor&act=rss",
        "name": "FM Korea 유머",
        "category": "entertainment",
        "locale": "ko",
    },
    {
        "url": "https://www.fmkorea.com/index.php?mid=computer_new&act=rss",
        "name": "FM Korea 컴퓨터",
        "category": "it",
        "locale": "ko",
    },
    {
        "url": "https://www.fmkorea.com/index.php?mid=politics_home1&act=rss",
        "name": "FM Korea 정치",
        "category": "politics",
        "locale": "ko",
    },
]


# ---------------------------------------------------------------------------
# SNS Reference Constants (used by sns_crawler.py)
# ---------------------------------------------------------------------------

REDDIT_SUBREDDITS: list[str] = [
    "worldnews",
    "technology",
    "korea",
    "kpop",
    "science",
    "news",
    "business",
    "stocks",
    "cryptocurrency",
    "gaming",
    "entertainment",
    "sports",
    "movies",
    "television",
    "music",
    "artificial",
    "machinelearning",
    "programming",
    "startups",
]

NITTER_INSTANCES: list[str] = [
    "nitter.net",
    "nitter.privacydev.net",
    "nitter.poast.org",
]


# ---------------------------------------------------------------------------
# Aggregated access
# ---------------------------------------------------------------------------

ALL_NEWS_FEEDS: list[FeedSource] = KR_NEWS_FEEDS + GLOBAL_NEWS_FEEDS + GOOGLE_TRENDS_FEEDS

ALL_FEEDS: list[FeedSource] = (
    KR_NEWS_FEEDS + GLOBAL_NEWS_FEEDS + GOOGLE_TRENDS_FEEDS + COMMUNITY_FEEDS
)

CATEGORIES: list[str] = ["politics", "economy", "it", "entertainment", "sports", "general"]
