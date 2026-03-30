export interface Filters {
  openNow: boolean
  hasTournament: boolean
  tournamentMonthFrom: number | null  // 1〜12, null = 全月
  tournamentMonthTo: number | null    // 1〜12, null = 全月

  near: boolean
  prefectures: string[]
  foodRich: boolean    // food_level = 'rich'
  manyTables: boolean  // table_count >= 6
  drinkRich: boolean   // drink_required = true
}
