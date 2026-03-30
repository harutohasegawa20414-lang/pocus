/**
 * seedData.ts をインポートして VenueDetail[] を JSON にダンプする
 * tsx (TypeScript executor) で実行する
 */
const fs = require('fs')
const path = require('path')

async function main() {
    // tsx で seedData.ts をダイナミックインポート
    const seedPath = path.resolve(__dirname, '..', 'ui', 'src', 'data', 'seedData.ts')

    // tsx / ts-node 経由で読む
    const mod = await import(seedPath)

    const venues = mod.ALL_SEED_VENUES
    const filterMap = mod.FILTER_MAP

    const results = venues.map(v => {
        const detail = mod.toVenueDetail(v)
        const card = mod.toVenueCard(v)
        const pin = mod.toVenuePin(v)
        const filters = filterMap[v.id] || {}
        return { ...detail, ...filters, _pin: pin, _card: card }
    })

    const outPath = path.resolve(__dirname, 'seed_venues.json')
    fs.writeFileSync(outPath, JSON.stringify(results, null, 2))
    console.log(`Wrote ${results.length} venues to ${outPath}`)
}

main().catch(e => { console.error(e); process.exit(1) })
