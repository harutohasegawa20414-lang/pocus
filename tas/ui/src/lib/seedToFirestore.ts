/**
 * シードデータ → Firestore 一括投入ユーティリティ
 *
 * ブラウザの開発者コンソールから以下のように実行:
 *   import('/src/lib/seedToFirestore.ts').then(m => m.seedAllToFirestore())
 *
 * または開発サーバー起動中にコンソールで:
 *   window.__seedFirestore()   // main.tsx で登録した場合
 */
import { ALL_SEED_VENUES, toVenuePin, toVenueCard, toVenueDetail } from '../data/seedData'
import { upsertVenue } from './firestore'

export async function seedAllToFirestore(): Promise<void> {
    console.log(`[seedToFirestore] ${ALL_SEED_VENUES.length} 件のシードデータを Firestore に書き込み開始...`)

    let ok = 0
    let fail = 0

    for (const sv of ALL_SEED_VENUES) {
        try {
            const pin = toVenuePin(sv)
            const card = toVenueCard(sv)
            const detail = toVenueDetail(sv)
            await upsertVenue(pin, card, detail)
            ok++
            console.log(`  ✔ [${ok}/${ALL_SEED_VENUES.length}] ${sv.name}`)
        } catch (err) {
            fail++
            console.error(`  ✘ ${sv.name}:`, err)
        }
    }

    console.log(`[seedToFirestore] 完了: 成功=${ok}, 失敗=${fail}`)
}
