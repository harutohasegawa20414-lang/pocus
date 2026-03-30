
# バグ・改善優先度レポート（完全版）
## POCUS（ポーカー店舗情報集約システム）— デプロイ前品質監査

**作成日:** 2026-03-23（Opus 4.6 による調査版）
**対象:** backend (FastAPI/SQLAlchemy) / frontend (React/TypeScript) / DB migrations / config — 全40+ファイル
**検出課題数:** 78件

---

## 目次

1. [CRITICAL — 本番稼働を即座に妨げる問題（14件）](#1-critical--本番稼働を即座に妨げる問題)
2. [HIGH — 機能不全・データ破損リスク（20件）](#2-high--機能不全データ破損リスク)
3. [MEDIUM — 品質・保守性・UX の問題（26件）](#3-medium--品質保守性ux-の問題)
4. [LOW — 技術的負債・設計改善（18件）](#4-low--技術的負債設計改善)
5. [サマリーテーブル（全件一覧）](#5-サマリーテーブル全件一覧)
6. [優先対応ロードマップ](#6-優先対応ロードマップ)
7. [付録：最も影響が大きい問題 TOP5](#7-付録最も影響が大きい問題-top5)

---

## 1. CRITICAL — 本番稼働を即座に妨げる問題

### C-01｜SQLAlchemy の interval 計算式が不正（クローラ全停止）
- **ファイル:** `tas/crawler/engine.py:44-48`
- **内容:**
  ```python
  Source.update_interval_hours * sa_text("interval '1 hour'")
  ```
- **問題:** `sa_text()` はテキスト SQL リテラルを返すだけで、`*` 演算子で掛け算はできない。この式はランタイムエラーまたは不正な SQL を生成する。
- **影響:** クローラのスケジュール判定が完全に動作しない。ソースの定期更新が一切行われない。

---

### C-02｜セッション管理の二重クローズ・二重コミット
- **ファイル:** `tas/db/session.py:26-35`
- **内容:**
  ```python
  async def get_session() -> AsyncGenerator[AsyncSession, None]:
      async with AsyncSessionLocal() as session:
          try:
              yield session
              await session.commit()      # ← 自動コミット
          except Exception:
              await session.rollback()
              raise
          finally:
              await session.close()       # ← async with が既に close するため二重
  ```
- **問題:**
  - `async with` のコンテキストマネージャと `finally` ブロックでセッションが二重クローズ
  - 読み取り専用 GET リクエストでも不要な `commit()` が走る
  - `report_venue` 等のエンドポイント内 `commit()` と合わせて二重コミット
- **影響:** 接続プールの不整合、パフォーマンス劣化、データ不整合の可能性。

---

### C-03｜デフォルトのシークレットキーがハードコード（セキュリティ）
- **ファイル:** `tas/config.py:36-37`
- **内容:**
  ```python
  api_secret_key: str = "change-me-in-production"
  admin_secret_key: str = "change-me-admin-secret"
  ```
- **問題:** `.env` を設定し忘れた場合、本番環境でこのデフォルト値が使われ、管理者 API が事実上誰でもアクセス可能になる。
- **矛盾する箇所:** `.env.example` にも同じデフォルト値が記載。

---

### C-04｜管理者認証がタイミング攻撃に脆弱
- **ファイル:** `tas/api/auth.py:12`
- **内容:**
  ```python
  if credentials.credentials != settings.admin_secret_key:
  ```
- **問題:** 通常の文字列比較を使用。攻撃者がレスポンス時間の差異からトークンを1文字ずつ推測できる。
- **修正方針:** `hmac.compare_digest()` を使用。

---

### C-05｜React Hooks の条件分岐前呼び出し違反（AdminDashboard クラッシュ）
- **ファイル:** `ui/src/pages/AdminDashboardPage.tsx:97`
- **内容:**
  ```tsx
  if (!authed) return <AdminLoginGate onAuth={() => setAuthed(true)} />

  // 99行目以降: これらのフックが条件付きで呼ばれる
  const load = useCallback(async () => { ... }, [])
  useEffect(() => { load() }, [load])
  ```
- **問題:** `if (!authed) return` がフック定義の前にあり、React Hooks ルール違反。`authed` が false→true に変わるとフック呼び出し順が変化し、ランタイムエラーが発生する。
- **影響:** AdminDashboard が認証成功後にクラッシュする可能性。

---

### C-06｜XSS 脆弱性 — MapView ポップアップへの未サニタイズ HTML 注入
- **ファイル:** `ui/src/components/MapView.tsx:154-171`
- **内容:**
  ```tsx
  marker.bindPopup(
    `<div>
      <p>${pin.display_name}</p>
      ${hoursHtml}${priceHtml}${tournamentHtml}
      <button onclick="window.__pocusNavigate('/venues/${pin.id}')">
    </div>`
  )
  ```
- **問題:** `pin.display_name`、`pin.next_tournament_title`、`pin.id` 等がサニタイズされずに HTML に埋め込まれている。
- **影響:** API レスポンスにスクリプトタグが含まれた場合、XSS 攻撃が成立する。

---

### C-07｜Admin API フォールバックによる認証バイパス
- **ファイル:** `ui/src/api/client.ts:262-304`
- **内容:**
  ```typescript
  export async function fetchAdminStats(): Promise<AdminStats> {
    try { return await adminGet<AdminStats>('/admin/stats') } catch {
      return { total_venues: 56, ... }  // エラー時にダミーを返す
    }
  }
  ```
- **問題:** 全 Admin API 関数が接続失敗時にダミーデータを返す。`AdminLoginGate` は `fetchAdminStats()` の成功をもってログイン成功とするため、**API 不通時に任意のトークンで管理画面にアクセス可能**。
- **影響:** 管理ダッシュボードの認証が事実上無意味。ダミーデータを本物と誤認する。

---

### C-08｜alembic.ini の DB 接続情報が config.py と全面不一致
- **ファイル:** `alembic.ini:5`
- **内容:**
  ```ini
  sqlalchemy.url = postgresql+asyncpg://tas:taspassword@localhost:5432/tasdb
  ```
- **問題:**
  - ユーザ名: `tas` vs `pocus`（config.py デフォルト）
  - DB名: `tasdb` vs `pocusdb`
  - パスワード: `taspassword` vs `""`
  - パスワード `taspassword` が平文でファイルに記載（Git コミットで漏洩）
- **影響:** `env.py` のインポート失敗時に間違った DB に接続するリスク。

---

### C-09｜三重データソースアーキテクチャ（Source of Truth 不明確）
- **ファイル:** `ui/src/api/client.ts`, `lib/firestore.ts`, `data/seedData.ts`
- **内容:** フロントエンドのデータ取得フロー:
  ```
  バックエンドAPI (PostgreSQL) → Firestore → seedData (ハードコード)
  ```
- **問題:**
  - Source of Truth が曖昧
  - Firestore とバックエンド DB の間に同期メカニズムが存在しない
  - フィルタリングロジックが SQL / Firestore(JS) / seedData(JS) の3箇所に重複実装
  - バックエンド未起動でもダミーデータで画面が表示される
- **影響:** データの一貫性が保証されない。管理者がダミーデータを本物と誤認する。

---

### C-10｜`window.__pocusNavigate` のグローバル関数注入
- **ファイル:** `ui/src/components/MapView.tsx:185-187`
- **内容:**
  ```tsx
  window.__pocusNavigate = (path: string) => navigate(path)
  ```
- **問題:** グローバルに登録された関数は任意の JS コードが上書き・呼び出し可能。ルーティングハイジャックが可能。
- **修正方針:** `marker.on('popupopen', ...)` でイベントリスナーを直接紐付ける。

---

### C-11｜alembic.ini に DB パスワードがハードコード（セキュリティ）
- **ファイル:** `alembic.ini:5`
- **問題:** `taspassword` が ini ファイルに平文記載。Git リポジトリにコミットされればパスワードが漏洩。
- **修正方針:** `sqlalchemy.url` をプレースホルダ値にし、`env.py` で環境変数から注入する設計に統一。

---

### C-12｜Firebase セキュリティルール未定義
- **ファイル:** `ui/src/lib/firebase.ts`, `lib/firestore.ts`
- **問題:** Firestore セキュリティルール (`firestore.rules`) の定義がプロジェクト内に確認できない。`upsertVenue` は `setDoc` で任意のドキュメントに書き込み可能。
- **影響:** Firestore Rules が未設定なら、ブラウザからの直接書き込みで全データが改竄される。

---

### C-13｜config.py のシークレットキー未設定時にサーバーが起動可能
- **ファイル:** `tas/config.py:36-37`, `.env.example`
- **問題:** `debug=False` でもデフォルト値「change-me-in-production」のままサーバーが起動できる。起動時バリデーションがない。
- **修正方針:** `@model_validator` で未変更時に `ValueError` を投げる。

---

### C-14｜CORS で `allow_origins=["*"]` と `allow_credentials=True` の同時設定
- **ファイル:** `tas/api/main.py:67-85`
- **問題:** `debug=True` 時にこの組み合わせが設定されるが、CORS 仕様上ブラウザが `Access-Control-Allow-Credentials: true` と `Access-Control-Allow-Origin: *` の同時設定を拒否する。
- **影響:** `debug=True` 時に認証付きリクエストが動作しない。

---

## 2. HIGH — 機能不全・データ破損リスク

### H-01｜ジオコーダのキャッシュが無制限に増大（メモリリーク）
- **ファイル:** `tas/crawler/geocoder.py:18`
- **内容:**
  ```python
  _cache: dict[str, tuple[float, float] | None] = {}
  ```
- **問題:** モジュールレベルのグローバル辞書で TTL やサイズ制限がない。長期稼働で無制限にメモリを消費。
- **修正方針:** `functools.lru_cache` や `cachetools.TTLCache` を使用。

### H-02｜Google Sheets API 呼び出しがイベントループをブロック
- **ファイル:** `tas/seeds/sheets.py:140-142`
- **内容:** `sync_to_db` は `async` メソッドだが、`read_pending_rows()` は同期的に Google Sheets API を呼ぶ。
- **影響:** asyncio イベントループがブロックされ、サーバー全体の他リクエストの処理が止まる。
- **修正方針:** `asyncio.to_thread()` でラップして非同期化。

### H-03｜月範囲フィルタが年をまたぐ場合に空結果を返す
- **ファイル:** `tas/api/routes/venue.py:66-79`, `map.py:82-95`
- **問題:** `tournament_month_from=11, tournament_month_to=2` で `month >= 11 AND month <= 2` となり結果が空。
- **修正方針:** 年をまたぐ場合は OR 条件にする。

### H-04｜`report_venue` で `entity_id` が無視されている
- **ファイル:** `tas/api/routes/venue.py:207-232`
- **問題:** `ReportCreate` の `entity_id` フィールドが無視され、URL の `venue_id` のみ使用。ボディの `entity_id` と URL が不一致でも処理される。

### H-05｜`_upsert_venue` で全 Venue を毎回メモリロード（パフォーマンス）
- **ファイル:** `tas/crawler/engine.py:255-268`
- **問題:** `limit(1000)` で最大1000件の Venue を全カラム分メモリにロード。1000件超で名寄せ漏れが発生する。

### H-06｜`handleBoundsChange` での stale state 参照
- **ファイル:** `ui/src/pages/HomePage.tsx:189-192`
- **内容:**
  ```tsx
  function handleBoundsChange(newBbox: string) {
    setBbox(newBbox)         // 非同期 → まだ反映されない
    if (viewMode === 'map') loadPins()  // 古い bbox で fetch
  }
  ```
- **影響:** 地図操作時に古いバウンディングボックスでデータ取得される。

### H-07｜useEffect 依存配列の不整合（eslint-disable で抑制）
- **ファイル:** `ui/src/pages/HomePage.tsx:179-182`
- **内容:**
  ```tsx
  useEffect(() => {
    if (viewMode === 'map') loadPins()
    else loadVenues(0)
  }, [viewMode, filters, userPos]) // eslint-disable-line react-hooks/exhaustive-deps
  ```
- **問題:** `loadPins` と `loadVenues` が依存配列に含まれていない。stale closure が発生。

### H-08｜レポート送信 API のレスポンス未確認
- **ファイル:** `ui/src/pages/VenueDetailPage.tsx:112-129`
- **問題:** `fetch` のレスポンスステータスを確認していない。404 や 500 が返っても「送信成功」として表示。

### H-09｜VenueDetail の `updated_at` 型不一致
- **ファイル:** `ui/src/types/api.ts:78 vs 45`
- **問題:** `VenueCard` では `updated_at: string | null` だが `VenueDetail` は `string`（null 除外）。実データで null が来るとランタイムエラー。

### H-10｜__pycache__ に旧ドメイン（タトゥースタジオ）のゴーストファイル残存
- **ファイル:** `tas/api/routes/__pycache__/`, `alembic/versions/__pycache__/`
- **問題:**
  - `artist.cpython-313.pyc` → ソース `artist.py` が存在しない
  - `studio.cpython-313.pyc` → ソース `studio.py` が存在しない
  - Alembic の旧マイグレーション（`0002_artist_sns_links` 等）の `.pyc` が残存
  - Python 3.11 と 3.13 の異なるキャッシュが混在
- **影響:** 旧バージョンのキャッシュが使われる可能性。マイグレーション履歴の不整合。

### H-11｜ORM models.py とマイグレーションの `ondelete` 不一致
- **ファイル:** `tas/db/models.py:189,236` vs `alembic/versions/0001_initial_schema.py`
- **問題:** マイグレーションでは `ondelete="CASCADE"` 設定だが、ORM モデルでは未設定。テスト用 sqlite 等で CASCADE 動作が欠落する。

### H-12｜フロントエンド/バックエンド AdminStats 型不一致
- **ファイル:** `tas/api/schemas.py` vs `ui/src/types/api.ts`
- **問題:** バックエンドの `AdminStats` に `disabled_sources` フィールドがあるがフロントエンドに未定義。

### H-13｜VenueCard / VenueDetail のフィールド過不足（型不一致）
- **ファイル:** `tas/api/schemas.py` vs `ui/src/types/api.ts`
- **問題:** バックエンドの `VenueCard` に `next_tournament_url`, `last_updated_at`, `data_age_days` があるがフロントエンドに未定義。`VenueDetail` にも `field_confidence`, `data_age_days` が欠落。

### H-14｜Admin API のサイレントフォールバックがダミーデータを表示
- **ファイル:** `ui/src/api/client.ts:262-328`
- **問題:** 全 Admin API がエラー時にハードコードされたダミーデータを返す。`resolveReport` も実際にはバックエンドに保存できないのに UI では成功表示。

### H-15｜geocoder, link_extractor のテストが存在しない
- **ファイル:** `tas/tests/` ディレクトリ
- **影響:** 位置情報処理と URL 抽出という重要機能にテストがない。

### H-16｜マイグレーション downgrade() でインデックスが削除されない
- **ファイル:** `alembic/versions/0001_initial_schema.py:223-230`
- **問題:** `upgrade()` で 13 個のインデックスを作成するが、`downgrade()` ではテーブルの `DROP TABLE` のみ。

### H-17｜MergeCandidateItem の型不一致
- **ファイル:** `tas/api/schemas.py` vs `ui/src/types/api.ts`
- **問題:** バックエンドに `resolved_at`, `resolved_by`, `resolution_note` があるがフロントエンドに未定義。

### H-18｜テストに旧ドメイン「tattoo」「タトゥー」の残骸
- **ファイル:** `tas/tests/test_fetcher.py:43-71`, `test_normalizer.py:39-45`
- **問題:** POCUS はポーカーシステムだがテストデータに「Tokyo Tattoo Studio」「渋谷タトゥー」等の旧ドメインデータ。

### H-19｜テストの年ハードコード「2025年」が将来失敗する可能性
- **ファイル:** `tas/tests/test_parser.py:250`
- **問題:** `TOURNAMENT_HTML` に「2025年4月1日」がハードコード。過去日付除外ロジックがあれば将来テスト失敗。

### H-20｜API ポートの不整合
- **ファイル:** `.env.example` vs `config.py` vs `AdminDashboardPage.tsx`
- **問題:**
  - `.env.example`: `API_PORT=8000`
  - `config.py`: `api_port=6002`
  - フロントエンド: 「ポート6002」の言及
- **影響:** 開発者が `.env.example` を参照するとポート 8000 で起動し、フロントエンドは 6002 を期待する。

---

## 3. MEDIUM — 品質・保守性・UX の問題

### M-01｜`open_now` フィルタが DB の静的フィールドのみで判定
- **ファイル:** `tas/api/routes/map.py:72-73`
- **問題:** `Venue.open_status == "open"` は DB の静的値（デフォルト `"unknown"`）。リアルタイム営業時間判定ではなく、実際に営業中の店舗が除外される。

### M-02｜`drink_rich` が `drink_required` で判定される意味の逆転
- **ファイル:** `tas/api/routes/venue.py:63`, `map.py:81`
- **問題:** パラメータ名 `drink_rich`（ドリンク充実）が `Venue.drink_required == True`（ワンドリンク制）でフィルタ。意味が逆。

### M-03｜`has_tournament` が DB 側でフィルタされず limit が不正確
- **ファイル:** `tas/api/routes/map.py:164-165`
- **問題:** Python 側でフィルタするため `limit` 指定件数より少ない結果が返る。`total` の値も不正。

### M-04｜クローラスケジューラの初回実行遅延
- **ファイル:** `tas/api/main.py:29-30`
- **問題:** `while True` ループ先頭で `await asyncio.sleep(...)` するため、起動後最初のクロールまで `scheduler_interval_minutes` 分待つ。

### M-05｜DB パスワード内の特殊文字がエスケープされない
- **ファイル:** `tas/config.py:29-31`
- **問題:** `postgres_password` に `@` や `/` 等が含まれると URL が不正になる。
- **修正方針:** `urllib.parse.quote_plus()` を使用。

### M-06｜VenueDetailPage の MOCK_VENUES が毎レンダー再作成
- **ファイル:** `ui/src/pages/VenueDetailPage.tsx:37-91`
- **問題:** コンポーネント関数内に定義され、`Date.now()` 使用で参照が毎回変化。

### M-07｜`venue.tournaments` が undefined 時のクラッシュ
- **ファイル:** `ui/src/pages/VenueDetailPage.tsx:159`
- **問題:** `venue.tournaments.filter(...)` で tournaments が undefined/null の場合ランタイムエラー。

### M-08｜seedData のランダムオフセットによるべき等性欠如
- **ファイル:** `ui/src/data/seedData.ts:536-537`
- **問題:** `toVenuePin` で `Math.random()` 座標オフセット。Firestore 書込み時に毎回データが変わる。

### M-09｜404 ルート（Not Found ページ）が存在しない
- **ファイル:** `ui/src/App.tsx`
- **問題:** `path="*"` のフォールバックルートがなく、存在しない URL で空白ページ表示。

### M-10｜React Error Boundary の欠如
- **ファイル:** `ui/src/App.tsx`
- **問題:** 子コンポーネントの未処理例外でアプリ全体がクラッシュ（白画面）。

### M-11｜`sessionStorage` への Admin トークン平文保存
- **ファイル:** `ui/src/api/client.ts:18-32`
- **問題:** XSS 脆弱性（C-06）が存在する状態で `sessionStorage` からトークン窃取が可能。

### M-12｜`resolveReport` のエラーハンドリングが 401 と他のエラーを区別しない
- **ファイル:** `ui/src/api/client.ts:306-328`
- **問題:** 認証失敗を含む全エラーでダミー `ReportItem` を返す。セッション切れでも成功表示。

### M-13｜FilterBar.tsx がコンポーネントではなく型定義のみ
- **ファイル:** `ui/src/components/FilterBar.tsx`
- **問題:** ファイル名と内容が不一致。`Filters` インターフェースの型定義のみ。

### M-14｜レポートフォームで `reporter_name`/`reporter_contact` が未収集
- **ファイル:** `ui/src/pages/VenueDetailPage.tsx` vs `tas/api/schemas.py`
- **問題:** バックエンドに `reporter_name`, `reporter_contact` があるがフロントエンドで未収集。匿名レポートのみ可能。

### M-15｜Tournament ステータス値 `finished` がバックエンドに未定義
- **ファイル:** `tas/db/models.py` vs `ui/src/pages/VenueDetailPage.tsx`
- **問題:** フロントのモックに `status: 'finished'` があるがバックエンドは `scheduled/canceled/unknown` のみ。

### M-16｜Firestore スキーマの型バリデーションなし
- **ファイル:** `ui/src/lib/firestore.ts`
- **問題:** `as VenuePin` 等の型アサーションのみ。スキーマ変更時にランタイムエラー。

### M-17｜セッション二重コミットの不統一（venue.py vs admin.py）
- **ファイル:** `tas/api/routes/venue.py`, `admin.py`, `db/session.py`
- **問題:** 一部ルートは明示的 `commit()`、他は `get_session()` の自動 `commit()` に依存。戦略が混在。

### M-18｜venues の `updated_at` に DB トリガーがない
- **ファイル:** `alembic/versions/0001_initial_schema.py:55-60`
- **問題:** ORM 経由の更新は `onupdate` で動作するが、直接 SQL では `updated_at` が更新されない。

### M-19｜tournaments テーブルに `updated_at` カラムがない
- **ファイル:** `alembic/versions/0001_initial_schema.py`, `tas/db/models.py`
- **問題:** `venues` と `sources` には `updated_at` があるが `tournaments` にはない。

### M-20｜`match_confidence` の `Numeric(3,2)` に CHECK 制約がない
- **ファイル:** `alembic/versions/0001_initial_schema.py:45`, `tas/db/models.py:79`
- **問題:** 0.00〜1.00 の範囲が想定されるが制約がなく、不正値の挿入が可能。

### M-21｜管理者 API の `limit` パラメータにバリデーションがない
- **ファイル:** `tas/api/routes/admin.py:102`
- **問題:** 大きな値を指定されると大量データが返される。`ge=1, le=200` 等のバリデーションが必要。

### M-22｜`_SKIP_PATH_RE` のデッドコードパターン
- **ファイル:** `tas/crawler/link_extractor.py:13`
- **問題:** `urlparse()` 後の `path` には `?` `#` は含まれないため `[?#]` がマッチしない。

### M-23｜`crawl_logs` テーブルに `crawled_at` のインデックスがない
- **ファイル:** `alembic/versions/0001_initial_schema.py:207-220`
- **問題:** ログの時系列検索やパージ処理でパフォーマンス低下。

### M-24｜`sources` テーブルの `canonical_url` にインデックスがない
- **ファイル:** `alembic/versions/0001_initial_schema.py:114-115`
- **問題:** 正規化 URL での重複チェック時のルックアップが遅くなる。

### M-25｜`VenuePin.display_name` がモデルに存在しないフィールド
- **ファイル:** `tas/api/schemas.py:100`, `routes/map.py:174`
- **問題:** `Venue` モデルには `display_name` がなく `name` を使用。`from_attributes=True` での直接変換は失敗する。

### M-26｜`_crawler_scheduler` がセッションのロールバックを保証しない
- **ファイル:** `tas/api/main.py:31-35`
- **問題:** `CrawlEngine` 内の `commit()` に依存するが、例外時のロールバックパターン (`try/except/rollback`) がない。

---

## 4. LOW — 技術的負債・設計改善

### L-01｜型注釈スタイルの混在（`Optional[str]` vs `str | None`）
### L-02｜`article` 要素のキーボードアクセシビリティ欠如（`tabIndex`, `role` 未設定）
### L-03｜モーダルのフォーカストラップ・Escape キー・ARIA 属性の未実装
### L-04｜PrefectureSection のトグル状態が `aria-expanded` 未設定
### L-05｜`new URL()` の例外ハンドリング未実装（AdminDashboardPage:365）
### L-06｜`lat=0` / `lng=0` の falsy チェックバグ（VenueDetailPage:322）
### L-07｜リクエストキャンセル（AbortController）未実装で race condition 発生リスク
### L-08｜`loading` ステートがマップピン取得とリスト取得で共有（状態不整合）
### L-09｜N+1 クエリパターン（admin.py の `get_stats` で 12 個の個別 COUNT クエリ）
### L-10｜ジオコーダのエラー時キャッシュ汚染（一時障害で永続的にキャッシュされる）
### L-11｜`read_pending_rows` の `int()` 変換が ValueError を投げる可能性
### L-12｜`_infer_open_status` の `next_day_flag` 判定が不明確
### L-13｜MapView のハードコード座標 `center={[35.6762, 139.6503]}`
### L-14｜API ベース URL `'/api'` のハードコード（環境変数から読むべき）
### L-15｜`main.tsx` の Non-null アサーション `document.getElementById('root')!`
### L-16｜`sources` 配列でのインデックスキー使用（VenueDetailPage:344）
### L-17｜tsconfig.app.json で `noUnusedLocals` / `noUnusedParameters` が `false`
### L-18｜`navigate` が依存配列に含まれるが直接使用されていない（MapView:183）

---

## 5. サマリーテーブル（全件一覧）

| ID | 重大度 | カテゴリ | タイトル | ファイル |
|---|---|---|---|---|
| C-01 | 🔴 CRITICAL | SQL | SQLAlchemy interval 計算式エラー | crawler/engine.py |
| C-02 | 🔴 CRITICAL | DB | セッション二重クローズ・二重コミット | db/session.py |
| C-03 | 🔴 CRITICAL | セキュリティ | シークレットキーのハードコード | config.py |
| C-04 | 🔴 CRITICAL | セキュリティ | タイミング攻撃に脆弱な認証 | api/auth.py |
| C-05 | 🔴 CRITICAL | React | Hooks 条件分岐違反 | AdminDashboardPage.tsx |
| C-06 | 🔴 CRITICAL | セキュリティ | XSS 脆弱性（MapView ポップアップ） | MapView.tsx |
| C-07 | 🔴 CRITICAL | セキュリティ | Admin API 認証バイパス | client.ts |
| C-08 | 🔴 CRITICAL | 設定 | alembic.ini の DB 接続不一致 | alembic.ini |
| C-09 | 🔴 CRITICAL | 設計 | 三重データソース（Source of Truth 不明確） | client.ts, firestore.ts |
| C-10 | 🔴 CRITICAL | セキュリティ | グローバル関数注入 | MapView.tsx |
| C-11 | 🔴 CRITICAL | セキュリティ | DB パスワードのハードコード | alembic.ini |
| C-12 | 🔴 CRITICAL | セキュリティ | Firebase セキュリティルール未定義 | firebase.ts |
| C-13 | 🔴 CRITICAL | セキュリティ | シークレット未設定でサーバー起動可能 | config.py |
| C-14 | 🔴 CRITICAL | CORS | allow_origins * と credentials 同時設定 | main.py |
| H-01 | 🟠 HIGH | メモリ | ジオコーダキャッシュ無制限増大 | geocoder.py |
| H-02 | 🟠 HIGH | 非同期 | Sheets API がイベントループブロック | sheets.py |
| H-03 | 🟠 HIGH | ロジック | 月範囲フィルタの年またぎ未対応 | venue.py, map.py |
| H-04 | 🟠 HIGH | バリデーション | entity_id 無視 | venue.py |
| H-05 | 🟠 HIGH | パフォーマンス | 全 Venue メモリロード | engine.py |
| H-06 | 🟠 HIGH | React | stale state 参照 | HomePage.tsx |
| H-07 | 🟠 HIGH | React | useEffect 依存配列不整合 | HomePage.tsx |
| H-08 | 🟠 HIGH | UX | レポート送信レスポンス未確認 | VenueDetailPage.tsx |
| H-09 | 🟠 HIGH | 型 | updated_at 型不一致 | api.ts |
| H-10 | 🟠 HIGH | ファイル | __pycache__ ゴーストファイル残存 | __pycache__/ |
| H-11 | 🟠 HIGH | DB | ondelete 不一致 | models.py |
| H-12 | 🟠 HIGH | 型 | AdminStats 型不一致 | schemas.py, api.ts |
| H-13 | 🟠 HIGH | 型 | VenueCard/Detail フィールド過不足 | schemas.py, api.ts |
| H-14 | 🟠 HIGH | UX | Admin API ダミーデータ表示 | client.ts |
| H-15 | 🟠 HIGH | テスト | テストカバレッジ不足 | tests/ |
| H-16 | 🟠 HIGH | DB | downgrade() インデックス未削除 | 0001_initial_schema.py |
| H-17 | 🟠 HIGH | 型 | MergeCandidateItem 型不一致 | schemas.py, api.ts |
| H-18 | 🟠 HIGH | テスト | 旧ドメインテストデータ残骸 | test_*.py |
| H-19 | 🟠 HIGH | テスト | 年ハードコードによる将来のテスト失敗 | test_parser.py |
| H-20 | 🟠 HIGH | 設定 | API ポート不整合 | .env.example, config.py |
| M-01 | 🟡 MEDIUM | ロジック | open_now フィルタが静的値のみ | map.py |
| M-02 | 🟡 MEDIUM | ロジック | drink_rich の意味逆転 | venue.py, map.py |
| M-03 | 🟡 MEDIUM | ロジック | has_tournament フィルタ不正確 | map.py |
| M-04 | 🟡 MEDIUM | 設計 | クローラ初回実行遅延 | main.py |
| M-05 | 🟡 MEDIUM | 設定 | パスワード特殊文字未エスケープ | config.py |
| M-06 | 🟡 MEDIUM | パフォーマンス | MOCK_VENUES 毎レンダー再作成 | VenueDetailPage.tsx |
| M-07 | 🟡 MEDIUM | Null | tournaments undefined クラッシュ | VenueDetailPage.tsx |
| M-08 | 🟡 MEDIUM | データ | seedData ランダムオフセット | seedData.ts |
| M-09 | 🟡 MEDIUM | UX | 404 ルートなし | App.tsx |
| M-10 | 🟡 MEDIUM | UX | Error Boundary なし | App.tsx |
| M-11 | 🟡 MEDIUM | セキュリティ | Admin トークン平文保存 | client.ts |
| M-12 | 🟡 MEDIUM | UX | resolveReport エラー区別なし | client.ts |
| M-13 | 🟡 MEDIUM | 設計 | FilterBar.tsx が型定義のみ | FilterBar.tsx |
| M-14 | 🟡 MEDIUM | UX | reporter_name/contact 未収集 | VenueDetailPage.tsx |
| M-15 | 🟡 MEDIUM | データ | Tournament status 'finished' 未定義 | models.py |
| M-16 | 🟡 MEDIUM | バリデーション | Firestore 型バリデーションなし | firestore.ts |
| M-17 | 🟡 MEDIUM | 設計 | コミット戦略の不統一 | session.py, routes/ |
| M-18 | 🟡 MEDIUM | DB | updated_at DB トリガーなし | 0001_initial_schema.py |
| M-19 | 🟡 MEDIUM | DB | tournaments に updated_at なし | models.py |
| M-20 | 🟡 MEDIUM | DB | match_confidence CHECK 制約なし | models.py |
| M-21 | 🟡 MEDIUM | バリデーション | limit パラメータ上限なし | admin.py |
| M-22 | 🟡 MEDIUM | デッドコード | _SKIP_PATH_RE の [?#] パターン | link_extractor.py |
| M-23 | 🟡 MEDIUM | DB | crawl_logs インデックスなし | 0001_initial_schema.py |
| M-24 | 🟡 MEDIUM | DB | canonical_url インデックスなし | 0001_initial_schema.py |
| M-25 | 🟡 MEDIUM | 設計 | display_name フィールド不在 | schemas.py |
| M-26 | 🟡 MEDIUM | DB | スケジューラのロールバック未保証 | main.py |
| L-01 | 🔵 LOW | 設計 | 型注釈スタイル混在 | 全体 |
| L-02 | 🔵 LOW | a11y | article キーボードアクセシビリティ | VenueCard.tsx |
| L-03 | 🔵 LOW | a11y | モーダルフォーカストラップなし | VenueDetailPage.tsx |
| L-04 | 🔵 LOW | a11y | aria-expanded 未設定 | HomePage.tsx |
| L-05 | 🔵 LOW | 例外処理 | new URL() 例外未処理 | AdminDashboardPage.tsx |
| L-06 | 🔵 LOW | ロジック | lat/lng falsy チェックバグ | VenueDetailPage.tsx |
| L-07 | 🔵 LOW | パフォーマンス | AbortController 未実装 | client.ts |
| L-08 | 🔵 LOW | UX | loading ステート共有 | HomePage.tsx |
| L-09 | 🔵 LOW | パフォーマンス | N+1 COUNT クエリ | admin.py |
| L-10 | 🔵 LOW | キャッシュ | ジオコーダエラーキャッシュ汚染 | geocoder.py |
| L-11 | 🔵 LOW | 例外処理 | int() ValueError リスク | sheets.py |
| L-12 | 🔵 LOW | ロジック | next_day_flag 判定不明確 | schemas.py |
| L-13 | 🔵 LOW | 設定 | MapView 座標ハードコード | MapView.tsx |
| L-14 | 🔵 LOW | 設定 | API BASE URL ハードコード | client.ts |
| L-15 | 🔵 LOW | 型 | Non-null アサーション | main.tsx |
| L-16 | 🔵 LOW | React | インデックスキー使用 | VenueDetailPage.tsx |
| L-17 | 🔵 LOW | 設定 | noUnusedLocals false | tsconfig.app.json |
| L-18 | 🔵 LOW | React | 不要な依存配列項目 | MapView.tsx |

**合計: 78件**（Critical: 14 / High: 20 / Medium: 26 / Low: 18）

---

## 6. 優先対応ロードマップ

### Phase 1 — 今すぐ修正（デプロイ前必須）

| 優先 | ID | 修正内容 | 想定工数 |
|---|---|---|---|
| 1 | C-01 | `func.make_interval()` を使った正しい interval 計算に書き換え | 15分 |
| 2 | C-03 | シークレットキーのデフォルト値削除 + 起動時バリデーション追加 | 10分 |
| 3 | C-07 | Admin API フォールバックのダミーデータ削除、エラーを throw | 20分 |
| 4 | C-05 | AdminDashboardPage の早期リターンをフック定義の後に移動 | 5分 |
| 5 | C-06 | MapView の HTML エスケープ関数追加、DOM ベースのポップアップに変更 | 30分 |
| 6 | C-04 | `hmac.compare_digest()` に変更 | 5分 |
| 7 | C-02 | `finally` の `session.close()` 削除、コミット戦略統一 | 15分 |
| 8 | C-08 | alembic.ini の sqlalchemy.url をプレースホルダ値に変更 | 5分 |
| 9 | C-14 | `debug=True` 時の CORS 設定修正（`allow_credentials=False` または特定オリジン） | 5分 |
| 10 | C-10 | `window.__pocusNavigate` を `marker.on()` に変更 | 20分 |

---

### Phase 2 — 今週中に修正（データ安全性・信頼性）

| 優先 | ID | 修正内容 |
|---|---|---|
| 11 | H-02 | `asyncio.to_thread()` で Sheets API を非同期化 |
| 12 | H-03 | 月範囲フィルタに年またぎ OR 条件を追加 |
| 13 | H-06 | `handleBoundsChange` で `loadPins` に bbox を引数渡し |
| 14 | H-07 | useEffect 依存配列を修正（eslint-disable 削除） |
| 15 | H-08 | レポート送信で `res.ok` チェック追加 |
| 16 | H-01 | ジオコーダキャッシュに `cachetools.TTLCache` 導入 |
| 17 | H-11 | ORM models.py に `ondelete="CASCADE"` 追加 |
| 18 | H-12,13,17 | フロントエンドの型定義をバックエンドと同期 |
| 19 | H-10 | `__pycache__` ディレクトリを全削除、インポート参照の検証 |
| 20 | H-20 | `.env.example` のポートを 6002 に統一 |

---

### Phase 3 — 今月中に対応（アーキテクチャ・保守性）

| ID | 修正内容 |
|---|---|
| C-09 | 三重データソースの整理（PostgreSQL を Source of Truth として明確化） |
| C-12 | `firestore.rules` を作成し書き込み権限を制限 |
| M-09 | 404 ルート追加 |
| M-10 | Error Boundary 追加 |
| H-15 | geocoder, link_extractor のテスト追加 |
| H-18 | テストデータをポーカードメインに更新 |
| M-02 | `drink_rich` フィルタのセマンティクスを正しいカラムに修正 |
| M-01 | `open_now` フィルタの動的判定を実装 |
| M-17 | コミット戦略を統一（get_session 自動コミット or 明示的コミット） |

---

### Phase 4 — 継続的改善（技術的負債）

| ID | 修正内容 |
|---|---|
| H-13 | OpenAPI スキーマからの型自動生成（`openapi-typescript`）導入 |
| M-23,24 | DB インデックスの追加マイグレーション作成 |
| L-07 | AbortController によるリクエストキャンセル実装 |
| L-09 | admin.py の COUNT クエリを1クエリに統合 |
| L-02,03,04 | アクセシビリティ改善 |
| M-08 | seedData のランダムオフセットを決定論的ハッシュに変更 |
| L-17 | tsconfig で `noUnusedLocals`/`noUnusedParameters` を `true` に変更 |

---

## 7. 付録：最も影響が大きい問題 TOP5

### #1 — クローラが完全に動作しない（C-01）
`Source.update_interval_hours * sa_text("interval '1 hour'")` は SQLAlchemy で動作しない。**ソースの定期更新スケジュール判定が全て失敗し、クローラの自動実行が一切行われない。**

### #2 — セキュリティが多層的に破綻（C-03 + C-04 + C-06 + C-07 + C-10 + C-11）
シークレットキーがハードコード、タイミング攻撃に脆弱、XSS でトークン窃取可能、Admin API がフォールバックで認証バイパス、`window.__pocusNavigate` でルーティングハイジャック可能、DB パスワードが平文。**攻撃者が管理者 API を直接操作し、データ改竄・システム操作が可能。**

### #3 — Admin ダッシュボードがクラッシュ（C-05）
React Hooks ルール違反により、認証成功後に `AdminDashboardPage` がランタイムエラーでクラッシュ。**管理者がダッシュボードを使用できない。**

### #4 — 三重データソースでデータ不整合（C-09 + H-14）
PostgreSQL → Firestore → seedData のフォールバックチェーンで Source of Truth が不明確。Admin API がダミーデータを返すため、管理者が偽データで運用判断を行う。**ユーザーに表示されるデータの正確性が保証されない。**

### #5 — フロントエンド/バックエンドの型乖離（H-12 + H-13 + H-17）
`AdminStats`、`VenueCard`、`VenueDetail`、`MergeCandidateItem` で複数のフィールド過不足。**バックエンドが返すデータをフロントエンドが正しく処理できず、表示欠落やランタイムエラーが発生。**

---

*本レポートは 2026-03-23 時点のコードを Opus 4.6 モデルで静的解析したものです。*
*全40+ファイルを4つの専門エージェントで並列調査し、結果を統合・重複排除しています。*
*実際の動作テスト（API 疎通確認・負荷テスト等）は別途実施を推奨します。*
